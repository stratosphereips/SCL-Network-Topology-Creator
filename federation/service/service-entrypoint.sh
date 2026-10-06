#!/bin/bash
# Unified service runtime entrypoint — data-driven from /opt/services.json.
#
# Starts the service daemons listed in $SERVICES (comma-separated), plus sshd
# and cron. The network plugin sets $SERVICES from the node's profile.service,
# so one image can act as any/all of the service hosts. Which command runs for
# each service id comes from /opt/services.json ("start"), the single source of
# truth shared with the build and the topology plugin's service picker.

set -e

# Node setup comes from a mounted config file (single source of truth) —
# not environment variables.
if [[ -f /opt/network-setup/node.conf ]]; then
  . /opt/network-setup/node.conf
fi

# The sim networks are docker-internal (no docker gateway): route through
# the topology router, which NATs internet-enabled networks.
if [[ -n "${GATEWAY_IP:-}" ]]; then
  ip route replace default via "$GATEWAY_IP" 2>/dev/null || true
fi

# Always start cron + ssh on a service host.
CRON_JOBS="*/3 * * * * apt-get update >/dev/null 2>&1"
# Merge traffic crontab lines baked into the node config.
if [[ -n "${EXTRA_CRON:-}" ]]; then
  CRON_JOBS="$CRON_JOBS
$EXTRA_CRON"
fi
echo "$CRON_JOBS" | crontab - 2>/dev/null || true
service cron start 2>/dev/null || true

mkdir -p /var/run/sshd
/usr/sbin/sshd

PIDS=()
SERVICES="${SERVICES:-}"

if [[ -f /opt/services.json ]]; then
  for sid in ${SERVICES//,/ }; do
    start_cmd=$(python3 -c "
import json, sys
d = json.load(open('/opt/services.json'))
print(d.get('services', {}).get('$sid', {}).get('start', ''))
" 2>/dev/null)
    if [[ -n "$start_cmd" ]]; then
      echo "[service-entrypoint] starting '$sid': $start_cmd"
      eval "$start_cmd"
      PIDS+=($!)
    else
      echo "[service-entrypoint] WARNING: no 'start' for service '$sid'" >&2
    fi
  done
else
  echo "[service-entrypoint] WARNING: /opt/services.json missing; no services started" >&2
fi

if [ ${#PIDS[@]} -gt 0 ]; then
  wait "${PIDS[@]}"
else
  # no services selected: keep the container alive
  tail -f /dev/null
fi
