#!/usr/bin/env bash
# Foreground supervisor for the ERPNext host stack (mirrors hospital-app-start.sh).
# Launched as the container's foreground process (exec'd by role_service_block in
# scripts.py) so a failed stack fails the container instead of hiding behind
# `tail -f /dev/null`.
#
# Stack: MariaDB(:3306) -> Redis(:6379) -> [first-boot: bench new-site + install-app
# erpnext + seed demo users/data] -> gunicorn(:8000) + worker + schedule + node
# socketio(:9000) -> nginx(:80).
# The MariaDB datadir AND the bench sites/ dir are on named volumes (compose.py);
# the seed-once gate creates the site only when the sites volume is fresh, so the
# site + data persist across topology stop/start cycles.
set -Eeuo pipefail

SITE=erpnext.localhost
ADMIN_PW=admin
DB_ROOT_PW=erpnextroot
BENCH=/home/frappe/frappe-bench
SITES="$BENCH/sites"
SITES_SEED="$BENCH/sites.seed"   # baked snapshot, OUTSIDE the sites volume mount
CHILD_PIDS=()

log() { printf '[erp-host] %s\n' "$*"; }

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

http_reachable() { curl -sS --max-time 5 -o /dev/null "$1"; }

# ── 1) MariaDB ─────────────────────────────────────────────────────────────────
install -d -o mysql -g mysql -m 0755 /var/run/mysqld
if command -v mariadbd-safe >/dev/null 2>&1; then
    mariadbd-safe --skip-syslog >/var/log/mariadb.log 2>&1 &
else
    mysqld_safe --skip-syslog >/var/log/mysql.log 2>&1 &
fi
CHILD_PIDS+=("$!")
wait_for MariaDB 60 mysqladmin ping --silent

# Idempotent admin login (fresh datadir uses unix_socket; after we set a password
# it requires one). Works across in-place restarts, not just fresh boots.
ADMIN=()
if mysql -uroot -e "SELECT 1" >/dev/null 2>&1; then
    ADMIN=(mysql -uroot)
elif mysql -uroot -p"$DB_ROOT_PW" -e "SELECT 1" >/dev/null 2>&1; then
    ADMIN=(mysql -uroot -p"$DB_ROOT_PW")
else
    log "ERROR: no working MariaDB administrative login"
    exit 1
fi

# Provision a password-bearing root on every root account (bench new-site connects
# as root over TCP with --db-root-password; unix_socket-only root would reject it).
"${ADMIN[@]}" <<SQL
ALTER USER 'root'@'localhost' IDENTIFIED BY '$DB_ROOT_PW';
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '$DB_ROOT_PW';
CREATE USER IF NOT EXISTS 'root'@'%'         IDENTIFIED BY '$DB_ROOT_PW';
ALTER USER 'root'@'127.0.0.1' IDENTIFIED BY '$DB_ROOT_PW';
ALTER USER 'root'@'%'         IDENTIFIED BY '$DB_ROOT_PW';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost'  WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%'          WITH GRANT OPTION;
FLUSH PRIVILEGES;
SQL

# ── 2) Restore the baked bench-sites skeleton if the sites volume is fresh. ─────
if [ ! -f "$SITES/common_site_config.json" ]; then
    log "fresh sites volume — restoring baked bench-sites skeleton"
    cp -a "$SITES_SEED/." "$SITES/"
    chown -R frappe:frappe "$SITES"
fi

# ── 3) Seed-once: create the site + install erpnext + seed demo users/data. ─────
SEEDED_FLAG="$SITES/$SITE/.erpnext-seeded"
run_bench() { runuser -u frappe -- bash -lc "cd '$BENCH' && $(printf '%q ' "$@")"; }

# ── 3a) Redis (single instance; common_site_config points cache/queue/socketio at
#        it). Started BEFORE new-site because `bench new-site --install-app erpnext`
#        runs the ERPNext migrations, which connect to redis_queue. ─────────────
redis-server --daemonize no --bind 127.0.0.1 --port 6379 \
    --save "" --appendonly no >/var/log/redis.log 2>&1 &
CHILD_PIDS+=("$!")
wait_for Redis 30 bash -lc 'redis-cli -h 127.0.0.1 -p 6379 ping | grep -q PONG'

if [ -f "$SEEDED_FLAG" ]; then
    log "site already provisioned (persistent volume) — skipping new-site/seed"
else
    log "provisioning site $SITE (new-site + install-app erpnext + seed) — ~3-5 min"
    # If a previous (failed) first boot left a half-created site dir + DB, tear it
    # down first so `new-site` isn't rejected with "Site ... already exists".
    if [ -d "$SITES/$SITE" ]; then
        OLD_DB=$(python3 -c "import json
try: print(json.load(open('$SITES/$SITE/site_config.json')).get('db_name',''))
except Exception: print('')" 2>/dev/null || true)
        log "removing partial site $SITE (db=${OLD_DB:-unknown}) before fresh new-site"
        rm -rf "$SITES/$SITE"
        [ -n "$OLD_DB" ] && mysql -uroot -p"$DB_ROOT_PW" \
            -e "DROP DATABASE IF EXISTS \`$OLD_DB\`;" >/dev/null 2>&1 || true
    fi
    # --install-app installs ERPNext doctypes during site creation (non-interactive).
    if ! run_bench bench new-site "$SITE" --admin-password "$ADMIN_PW" \
            --db-root-password "$DB_ROOT_PW" --install-app erpnext \
            > /var/log/erpnext-newsite.log 2>&1; then
        log "new-site failed — tail of log:"
        tail -n 80 /var/log/erpnext-newsite.log || true
        exit 1
    fi
    run_bench bench use "$SITE" >/dev/null 2>&1 || true
    # Seed known users at each privilege level + sample business data.
    # (bench execute can't take a file:func path — it evals a dotted module path —
    # so run the seed via env/bin/python + run_seed.py, which inits frappe itself.)
    if ! runuser -u frappe -- bash -lc "cd '$BENCH/sites' && ../env/bin/python /usr/local/bin/run_seed.py '$SITE'" \
            > /var/log/erpnext-seed.log 2>&1; then
        log "WARN: seed script failed (non-fatal) — tail:"
        tail -n 60 /var/log/erpnext-seed.log || true
    fi
    touch "$SEEDED_FLAG"
    chown frappe:frappe "$SEEDED_FLAG" 2>/dev/null || true
fi

# Frappe resolves the site purely from the Host header (site = Host, no
# wildcard/fallback), so a request whose Host is an IP / 127.0.0.1 / hostname
# 404s ("<host> does not exist"). Symlink the site dir to EVERY access host so
# any of them resolves to erpnext.localhost (nginx ALSO forces Host to the site
# name, so :80 is covered regardless). Idempotent.
if [ -d "$SITES/$SITE" ]; then
    mapfile -t ALIASES < <(printf '%s\n' \
        "127.0.0.1" "localhost" "$(hostname 2>/dev/null || true)" \
        $(hostname -I 2>/dev/null || true))
    for alias in "${ALIASES[@]}"; do
        [ -z "$alias" ] && continue
        [ "$alias" = "$SITE" ] && continue
        ln -sfn "$SITE" "$SITES/$alias" 2>/dev/null || true
        chown -h frappe:frappe "$SITES/$alias" 2>/dev/null || true
    done
fi

touch /tmp/erp-seed-ready
log "site ready (seeded)"

# ── 5) gunicorn web (:8000) as frappe (critical). ──────────────────────────────
(
    cd "$BENCH"
    exec gosu frappe env/bin/gunicorn frappe.app:application \
        --chdir sites --bind 127.0.0.1:8000 \
        --workers 4 --threads 4 --timeout 120 \
        --graceful-timeout 120 --log-level info
) >/var/log/erpnext-gunicorn.log 2>&1 &
CHILD_PIDS+=("$!")

if ! wait_for gunicorn 90 http_reachable http://127.0.0.1:8000/api/method/ping; then
    tail -n 120 /var/log/erpnext-gunicorn.log || true
    exit 1
fi

# ── 5b) Background workers + scheduler + node socketio (best-effort, respawn). ──
# These are NOT in CHILD_PIDS: a crashing worker must not tear down the web stack.
( cd "$BENCH" && while true; do
        gosu frappe bash -lc "cd '$BENCH' && bench --site '$SITE' worker --queue long,default,short" \
            >/var/log/erpnext-worker.log 2>&1 || true
        sleep 5
    done ) &
( cd "$BENCH" && while true; do
        gosu frappe bash -lc "cd '$BENCH' && bench --site '$SITE' schedule" \
            >/var/log/erpnext-schedule.log 2>&1 || true
        sleep 5
    done ) &
if [ -f "$BENCH/apps/frappe/socketio.js" ]; then
    ( cd "$BENCH" && while true; do
          gosu frappe bash -lc "cd '$BENCH' && node apps/frappe/socketio.js" \
              >/var/log/erpnext-socketio.log 2>&1 || true
          sleep 5
      done ) &
fi

# ── 6) nginx front door (:80 -> gunicorn :8000). ───────────────────────────────
nginx -t 2>/var/log/nginx-test.log || cat /var/log/nginx-test.log
nginx -g 'daemon off;' >/var/log/nginx.log 2>&1 &
CHILD_PIDS+=("$!")
wait_for nginx 20 http_reachable http://127.0.0.1/api/method/ping

touch /tmp/erp-stack-ready
log "stack ready: front door :80, gunicorn :8000, DB :3306, redis :6379"

# Return as soon as any critical child dies; EXIT cleanup terminates the rest.
wait -n "${CHILD_PIDS[@]}"
log "ERROR: a critical process exited"
exit 1
