#!/usr/bin/env bash
# Foreground supervisor for the Leosac host stack (mirrors erpnext-app-start.sh).
# Launched as the container's foreground process (exec'd by role_service_block in
# scripts.py) so a failed stack fails the container instead of hiding behind
# `tail -f /dev/null`.
#
# Stack: PostgreSQL(:5432) -> leosac core + websock-api(:8888, schema auto-created
# on first start) -> [first-boot: leosac-create-admin + seed_leosac.py demo
# users/doors/credentials] -> nginx(:80, Ember UI with boot-time backend-address
# rewrite). The PostgreSQL datadir is on a named volume (compose.py); the
# seed-once gate only creates data when that volume is fresh, so everything
# persists across topology stop/start cycles.
set -Eeuo pipefail

DB_USER=leosac
DB_PASS=leosac123
DB_NAME=leosac
SEED_MARKER=/var/lib/postgresql/16/main/.scl-leosac-seeded
WEB_DIST=/opt/leosac-web-dist
WEB_ROOT=/var/www/leosac
WS_PLACEHOLDER=ws://leosac.internal:8888
CHILD_PIDS=()

log() { printf '[leosac-host] %s\n' "$*"; }

cleanup() {
    local status=$?
    trap - EXIT INT TERM
    if ((${#CHILD_PIDS[@]})); then
        kill "${CHILD_PIDS[@]}" 2>/dev/null || true
        sleep 3
        kill -KILL "${CHILD_PIDS[@]}" 2>/dev/null || true
    fi
    exit "$status"
}
trap cleanup EXIT INT TERM

wait_for() {
    local name="$1" attempts="$2"
    shift 2
    for _ in $(seq 1 "$attempts"); do
        if "$@" >/dev/null 2>&1; then
            log "$name is ready"
            return 0
        fi
        sleep 2
    done
    log "ERROR: $name did not become ready"
    return 1
}

# ── 1) PostgreSQL (child of the supervisor, so wait -n covers it). ────────────
install -d -o postgres -g postgres -m 02775 /var/run/postgresql
gosu postgres /usr/lib/postgresql/16/bin/postgres \
    -D /var/lib/postgresql/16/main \
    -c config_file=/etc/postgresql/16/main/postgresql.conf \
    >/var/log/postgresql.log 2>&1 &
CHILD_PIDS+=("$!")
wait_for PostgreSQL 90 pg_isready -q

# Idempotent weak-cred provisioning (works on restarts, not just fresh volumes).
# SUPERUSER so leosac's schema versioning can DDL; weak planted creds are the
# point of the lab target (same convention as the erpnext/db-server hosts).
gosu postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
        CREATE ROLE ${DB_USER} LOGIN SUPERUSER PASSWORD '${DB_PASS}';
    END IF;
END \$\$;
SQL
if ! gosu postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    gosu postgres createdb -O "${DB_USER}" "${DB_NAME}"
fi
gosu postgres psql -v ON_ERROR_STOP=1 -c "ALTER ROLE ${DB_USER} WITH LOGIN SUPERUSER PASSWORD '${DB_PASS}';"

# ── 2) leosac core (child; creates/upgrades the DB schema on startup). ────────
/usr/local/bin/leosac -k /etc/leosac.d/kernel.xml >/var/log/leosac.log 2>&1 &
CHILD_PIDS+=("$!")
wait_for websock-api 60 nc -w1 -z 127.0.0.1 8888

# ── 3) Seed-once: first admin + demo users/doors/credentials. ────────────────
if [ -f "$SEED_MARKER" ]; then
    log "stack already seeded (persistent volume) — skipping admin/seed"
else
    log "first boot: creating admin user + seeding demo data"
    if ! /usr/local/bin/leosac-create-admin admin admin; then
        log "ERROR: leosac-create-admin failed — tail of leosac log:"
        tail -n 60 /var/log/leosac.log || true
        exit 1
    fi
    if ! python3 /usr/local/bin/seed_leosac.py >/var/log/leosac-seed.log 2>&1; then
        log "WARN: seed script failed (non-fatal) — tail:"
        tail -n 60 /var/log/leosac-seed.log || true
    fi
    touch "$SEED_MARKER"
    chown postgres:postgres "$SEED_MARKER" 2>/dev/null || true
fi
touch /tmp/leosac-seed-ready

# ── 4) Web UI: copy baked dist + rewrite the baked backend address. ──────────
# LEOSAC_ADDR is baked into the Ember bundle at image-build time as a
# placeholder; rewrite it to this container's hostname (= the compose service
# name, DNS-resolvable inside the topology network). index.html carries the
# address URL-ENCODED inside the inline config blob (%3A%2F%2F...), so both
# forms must be replaced — the browser reads the encoded one. Browsers can
# still override at runtime via localStorage.leosacAddr.
if [ ! -f "$WEB_ROOT/index.html" ]; then
    mkdir -p "$WEB_ROOT"
    cp -a "$WEB_DIST/." "$WEB_ROOT/"
fi
HOST_WS_ADDR="ws://$(hostname):8888"
HOST_WS_ENC="ws%3A%2F%2F$(hostname)%3A8888"
PLACEHOLDER_ENC='ws%3A%2F%2Fleosac.internal%3A8888'
if grep -rql -e "$WS_PLACEHOLDER" -e "$PLACEHOLDER_ENC" "$WEB_ROOT"; then
    grep -rl -e "$WS_PLACEHOLDER" -e "$PLACEHOLDER_ENC" "$WEB_ROOT" | while read -r f; do
        sed -i -e "s|$WS_PLACEHOLDER|$HOST_WS_ADDR|g" \
               -e "s|$PLACEHOLDER_ENC|$HOST_WS_ENC|g" "$f"
    done
    log "rewrote backend address to $HOST_WS_ADDR"
fi

# Win condition for the engagement (web-host proof.txt convention).
install -d -m 0755 /srv/samlab
printf 'FLAG{leosac-admin-admin-and-pgsql-leosac123}\n' > /srv/samlab/proof.txt
chmod 0644 /srv/samlab/proof.txt

# ── 5) nginx front door (:80 -> static Ember dist). ──────────────────────────
nginx -t 2>/var/log/nginx-test.log || cat /var/log/nginx-test.log
nginx -g 'daemon off;' >/var/log/nginx.log 2>&1 &
CHILD_PIDS+=("$!")
wait_for nginx 20 curl -fsS --max-time 5 -o /dev/null http://127.0.0.1/

touch /tmp/leosac-stack-ready
log "stack ready: web :80, websock-api :8888, PostgreSQL :5432"

# Fail as soon as any critical child dies (poll, not `wait -n`: a PID bash has
# already reaped makes wait -n error out with "no such job" instead of failing
# the container — exactly what happened when the leosac daemon crashed during
# the first seeding attempts). EXIT cleanup terminates the rest.
while :; do
    for pid in "${CHILD_PIDS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            log "ERROR: critical process $pid exited"
            exit 1
        fi
    done
    sleep 5
done
