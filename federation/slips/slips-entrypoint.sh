#!/bin/bash
set -e

# Node setup comes from a mounted config file (single source of truth) —
# not environment variables. When present, the node is plugin-managed:
# crons/keepalive targets come from node.conf only (EXTRA_CRON,
# KEEPALIVE_TARGETS, GATEWAY_IP) and the hardcoded standalone defaults
# below are skipped, so plugin deployments never run duplicate or
# wrong-IP traffic. Without node.conf (standalone fixed experiment) the
# original hardcoded hostname behavior is kept.
MANAGED=0
if [[ -f /opt/network-setup/node.conf ]]; then
  . /opt/network-setup/node.conf
  MANAGED=1
fi

# The sim networks are docker-internal (no docker gateway): route through
# the topology router, which NATs internet-enabled networks. p2p_trust also
# needs a default route to learn its own IP.
if [[ -n "${GATEWAY_IP:-}" ]]; then
  ip route replace default via "$GATEWAY_IP" 2>/dev/null || true
fi

# The p2p4slips "pigeon" uses libp2p mDNS for peer discovery; docker container
# net namespaces come without a multicast route, so libp2p dies with
# "No multicast listeners could be started" and p2p_trust exits. Add the
# multicast route on EVERY up non-loopback interface (these peers may have
# no default route at all, so a default-derived iface can be empty).
{
  for _i in $(ip -o link show up | awk -F': ' '$2!="lo"{print $2}' | cut -d@ -f1); do
    ip route replace 224.0.0.0/4 dev "$_i" 2>/dev/null || ip route add 224.0.0.0/4 dev "$_i" 2>/dev/null || true
  done
} 2>/dev/null || true

# Hostname-specific traffic generation cronjobs (standalone mode only —
# plugin-managed nodes get their connections via EXTRA_CRON)
HOSTNAME=$(hostname)

# Start with apt update every 3 minutes for all slips nodes
CRON_JOBS="*/3 * * * * apt-get update >/dev/null 2>&1"

if [[ "$MANAGED" -eq 0 ]]; then
    case "$HOSTNAME" in
        slips-1)
            # Check FTP server (ubuntu-1) every minute
            CRON_JOBS="$CRON_JOBS
* * * * * /scripts/check-ftp.sh 172.20.1.2 21 >/dev/null 2>&1"
            # Access Wikipedia every 5 minutes
            CRON_JOBS="$CRON_JOBS
*/5 * * * * /scripts/internet-traffic.sh wikipedia >/dev/null 2>&1"
            ;;
        slips-2)
            # Access ubuntu-2 website every 2 minutes
            CRON_JOBS="$CRON_JOBS
*/2 * * * * /scripts/curl-website.sh http://172.20.1.3:8000 >/dev/null 2>&1"
            # Access Google every 7 minutes (different from slips-1)
            CRON_JOBS="$CRON_JOBS
*/7 * * * * /scripts/internet-traffic.sh google >/dev/null 2>&1"
            ;;
        slips-3)
            # Access slips-1 website every 4 minutes
            CRON_JOBS="$CRON_JOBS
*/4 * * * * /scripts/curl-website.sh http://172.20.1.5:8000 >/dev/null 2>&1"
            # Access Wikipedia every 10 minutes (different frequency)
            CRON_JOBS="$CRON_JOBS
*/10 * * * * /scripts/internet-traffic.sh wikipedia >/dev/null 2>&1"
            ;;
    esac
fi

# Merge traffic crontab lines passed by the network plugin (EXTRA_CRON).
if [[ -n "${EXTRA_CRON:-}" ]]; then
  CRON_JOBS="$CRON_JOBS
$EXTRA_CRON"
fi

echo "$CRON_JOBS" | crontab -

# Start cron daemon
service cron start

mkdir -p /var/run/sshd /var/run/apache2 /var/run/redis
/usr/sbin/sshd

# Redis is started and managed by SLIPS itself (with its generated auth).

if [[ "${RUN_WEB:-0}" == "1" ]] && [[ -f /var/www/slips_site/index.html ]]; then
  rm -rf /var/www/html
  ln -s /var/www/slips_site /var/www/html

  cat >/etc/apache2/ports.conf <<'EOF'
Listen 8000
EOF

  cat >/etc/apache2/sites-available/000-default.conf <<'EOF'
<VirtualHost *:8000>
    ServerName slips-1
    DocumentRoot /var/www/slips_site
    ErrorLog ${APACHE_LOG_DIR}/error.log
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
EOF

  if command -v apache2ctl >/dev/null 2>&1; then
    /usr/sbin/apache2ctl -D FOREGROUND &
    APACHE_PID=$!
  fi
fi

cd /opt/StratosphereLinuxIPS

# Clear stale bytecode caches so modules recompile from source
python3 -c "
import os
for root, dirs, files in os.walk('/opt/StratosphereLinuxIPS'):
    if '__pycache__' in dirs:
        pyc_path = os.path.join(root, '__pycache__')
        for pyc_file in os.listdir(pyc_path):
            os.remove(os.path.join(pyc_path, pyc_file))
        os.rmdir(pyc_path)
print('[entrypoint] Cleared __pycache__ directories')
" 2>/dev/null || true

mkdir -p /var/log/slips /var/log/slips_output /opt/StratosphereLinuxIPS/config/p2p

HOSTNAME=$(hostname)
PEER_PORT=6668

# Build the peer multiaddress list from SLIPS_PEERS (propagated by the network
# plugin / runner from the topology manifest). We use Docker's embedded DNS
# (/dns4/<hostname>) so no IPs are hardcoded and reruns stay deterministic:
# hostnames come from the manifest and the plugin assigns stable IPs.
PEER_NAMES=()
if [[ -n "${SLIPS_PEERS:-}" ]]; then
  IFS=',' read -ra PEER_NAMES <<< "$SLIPS_PEERS"
else
  PEER_NAMES=("slips-1" "slips-2" "slips-3")
fi

# All peers share the same multiaddress list (every peer knows everyone).
{
  printf 'Identity:\n  GenerateNewKey: false\n'
  printf 'PeerDiscovery:\n  DisableBootstrappingNodes: false\n  ListOfMultiAddresses:\n'
  for n in "${PEER_NAMES[@]}"; do
    printf '    - "/dns4/%s/tcp/%s/p2p/slips-p2p"\n' "$n" "$PEER_PORT"
  done
  printf 'Redis:\n  Host: 127.0.0.1\n  Port: 6379\n  Tl2NlChannel: iris_internal\n'
  printf 'Server:\n  DhtServerMode: true\n  Host: null\n  Port: %s\n' "$PEER_PORT"
} > /opt/StratosphereLinuxIPS/config/p2p/p2p_config.yaml

# Select the federated peer config by SLIPS_PROFILE (set by the network plugin
# from the machine profile's slips_variant). Variants share the federation
# module settings and differ only in which detection modules are disabled.
if [[ -n "${SLIPS_PROFILE:-}" ]] && [[ -f "/opt/StratosphereLinuxIPS/config/slips_p2p_${SLIPS_PROFILE}.yaml" ]]; then
  cp "/opt/StratosphereLinuxIPS/config/slips_p2p_${SLIPS_PROFILE}.yaml" /opt/StratosphereLinuxIPS/config/slips_p2p.yaml
  echo "[entrypoint] Using SLIPS_PROFILE=${SLIPS_PROFILE} config"
elif [[ ! -f /opt/StratosphereLinuxIPS/config/slips_p2p.yaml ]]; then
  cp /opt/StratosphereLinuxIPS/config/slips_p2p_strong.yaml /opt/StratosphereLinuxIPS/config/slips_p2p.yaml
  echo "[entrypoint] No SLIPS_PROFILE; using default (strong) config"
else
  echo "[entrypoint] Using mounted slips_p2p.yaml"
fi

# slips_p2p.yaml is baked into the image (or mounted per-host).

cd /opt/StratosphereLinuxIPS
# p2p4slips is prebuilt by the SLIPS image build.

echo "[P2P] Starting SLIPS on $HOSTNAME with P2P enabled"
echo "[P2P] Peer multiaddress: /ip4/$(hostname -I | awk '{print $1}')/tcp/$PEER_PORT/p2p/slips-p2p"

# Start background traffic generator to keep interface active and prevent Zeek timeout
# This generates periodic internal network traffic for SLIPS to analyze
# Standalone (fixed experiment): the original hardcoded targets. Managed
# (plugin): targets from node.conf (KEEPALIVE_TARGETS, resolved from the
# live topology) and the topology router as ping gateway.
if [[ "$MANAGED" -eq 1 ]]; then
    KEEPALIVE="${KEEPALIVE_TARGETS:-}"
    PING_TARGET="${GATEWAY_IP:-}"
else
    KEEPALIVE="http://172.20.1.2:21 http://172.20.1.3:8000 http://172.20.1.5:8000"
    PING_TARGET="172.20.1.1"
fi
(
  while true; do
    # Generate some internal traffic every 30 seconds
    for _t in $KEEPALIVE; do
        curl -s --connect-timeout 2 "$_t" >/dev/null 2>&1 || true
    done
    sleep 30
  done
) &
TRAFFIC_GEN_PID=$!

# Also run constant low-volume ping to keep Zeek happy (every 5 seconds)
(
  while true; do
    if [[ -n "$PING_TARGET" ]]; then
        # Simple ping to gateway to keep interface active
        ping -c 1 -W 2 "$PING_TARGET" >/dev/null 2>&1 || true
    fi
    sleep 5
  done
) &
PING_PID=$!

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export KMP_BLOCKTIME=0
export OPENBLAS_NUM_THREADS=1
echo "[P2P] Thread limits: OMP_NUM_THREADS=$OMP_NUM_THREADS MKL_NUM_THREADS=$MKL_NUM_THREADS"

# Force multiprocessing "spawn" to avoid PyTorch fork-safety crashes
# https://pytorch.org/docs/stable/notes/multiprocessing.html
python3 -c "import multiprocessing; multiprocessing.set_start_method('spawn', force=True)" 2>/dev/null || true
echo "[P2P] Multiprocessing start method set to spawn"

python3 slips.py -c config/slips_p2p.yaml -i eth0 -o /var/log/slips_output >/var/log/slips/slips.log 2>&1 &
SLIPS_PID=$!

if [[ "${RUN_WEB:-0}" == "1" ]]; then
  wait $SLIPS_PID $APACHE_PID
else
  wait $SLIPS_PID
fi

# Cleanup on exit
kill $TRAFFIC_GEN_PID $PING_PID 2>/dev/null || true
