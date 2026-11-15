#!/usr/bin/env bash
# Foreground supervisor for the Greedy Cars lab stack.
set -Eeuo pipefail

DB_NAME=greedy_cars_db
DB_USER=greedy_cars
DB_PW=adminAdmin
CHILD_PIDS=()

log() {
    printf '[greedy-host] %s\n' "$*"
}

cleanup() {
    local status=$?
    trap - EXIT INT TERM
    if ((${#CHILD_PIDS[@]})); then
        kill "${CHILD_PIDS[@]}" 2>/dev/null || true
        # Some Spring/MariaDB shutdown hooks can wait indefinitely. Give them
        # a short grace period, then guarantee that PID 1 terminates.
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

http_reachable() {
    curl -sS --max-time 3 -o /dev/null "$1"
}

http_success() {
    curl -fsS --max-time 3 -o /dev/null "$1"
}

start_war() {
    local name="$1" war="$2" port="$3" context="$4" logfile="$5"
    shift 5
    env \
        SERVER_PORT="$port" \
        SERVER_SERVLET_CONTEXT_PATH="$context" \
        SPRING_DATASOURCE_URL="$DS_URL" \
        SPRING_DATASOURCE_USERNAME="$DB_USER" \
        SPRING_DATASOURCE_PASSWORD="$DB_PW" \
        "$@" \
        java -Xmx384m -jar "$war" >"$logfile" 2>&1 &
    local pid=$!
    CHILD_PIDS+=("$pid")
    log "started $name (pid $pid)"
}

install -d -o mysql -g mysql -m 0755 /var/run/mysqld
if command -v mariadbd-safe >/dev/null 2>&1; then
    mariadbd-safe --skip-syslog >/var/log/mariadb.log 2>&1 &
else
    mysqld_safe --skip-syslog >/var/log/mysql.log 2>&1 &
fi
CHILD_PIDS+=("$!")
wait_for MariaDB 60 mysqladmin ping --silent

ADMIN=()
if mysql -uroot -e "SELECT 1" >/dev/null 2>&1; then
    ADMIN=(mysql -uroot)
elif mysql -uroot -p"$DB_PW" -e "SELECT 1" >/dev/null 2>&1; then
    ADMIN=(mysql -uroot -p"$DB_PW")
else
    log "ERROR: no working MariaDB administrative login"
    exit 1
fi
"${ADMIN[@]}" <<SQL
CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PW';
CREATE USER IF NOT EXISTS '$DB_USER'@'127.0.0.1' IDENTIFIED BY '$DB_PW';
CREATE USER IF NOT EXISTS '$DB_USER'@'%' IDENTIFIED BY '$DB_PW';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'127.0.0.1';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'%';
FLUSH PRIVILEGES;
SQL

DS_URL="jdbc:mariadb://localhost:3306/${DB_NAME}?useUnicode=true&characterEncoding=utf8&serverTimezone=America/Argentina/Mendoza"
# JWT signing key for the API tier. The image build scrubs app.jwt.secret to
# `not-configured` (14 bytes = 112 bits) for secret hygiene — jjwt rejects any
# HMAC-SHA key < 256 bits, so leaving the default makes /api/auth/login 500 on
# EVERY successful password check and form login rejects all users. Supply a
# >=256-bit key here (or via APP_JWT_SECRET in the container env) to complete
# the "runtime values arrive through env" wiring the Dockerfile assumes.
JWT_SECRET="${APP_JWT_SECRET:-scl-lab-greedy-cars-hs256-signing-key-2026-v1}"
start_war greedy_cars /srv/wars/greedy_cars.war 9000 /greedy_cars /var/log/greedy_cars.log \
    TWILIO_ACCOUNT_SID=AC00000000000000000000000000000000 \
    TWILIO_AUTH_TOKEN=dummy_token_not_real \
    APP_JWT_SECRET="$JWT_SECRET"
if ! wait_for greedy_cars 90 http_reachable http://127.0.0.1:9000/greedy_cars/api; then
    tail -n 100 /var/log/greedy_cars.log || true
    exit 1
fi

mysql -u"$DB_USER" -p"$DB_PW" "$DB_NAME" \
    < /usr/local/share/greedy-seed.sql
touch /tmp/greedy-seed-ready
log "idempotent demo dataset is ready"

API_BASE=http://localhost:9000/greedy_cars/api
start_war greedy_institucional /srv/wars/greedy_institucional.war 8080 /greedy_institucional /var/log/greedy_institucional.log \
    GREEDY_API_BASE_URL="$API_BASE" GREEDY_API_USERNAME=admin GREEDY_API_PASSWORD='GreedyAdmin123!'
start_war gredy_cars_client /srv/wars/gredy_cars_client.war 8081 /gredy_cars_client /var/log/gredy_cars_client.log \
    GREEDY_API_BASE_URL="$API_BASE" GREEDY_API_USERNAME=admin GREEDY_API_PASSWORD='GreedyAdmin123!'

if ! wait_for greedy_institucional 90 http_success http://127.0.0.1:8080/greedy_institucional/; then
    tail -n 100 /var/log/greedy_institucional.log || true
    exit 1
fi
if ! wait_for gredy_cars_client 90 http_success http://127.0.0.1:8081/gredy_cars_client/; then
    tail -n 100 /var/log/gredy_cars_client.log || true
    exit 1
fi

nginx -t
nginx -g 'daemon off;' >/var/log/nginx.log 2>&1 &
CHILD_PIDS+=("$!")
wait_for nginx 15 http_success http://127.0.0.1/gredy_cars_client/
touch /tmp/greedy-stack-ready
log "stack ready: front door :80, API :9000, institutional :8080, client :8081, DB :3306"

# Bash returns as soon as any critical child dies; EXIT cleanup terminates the
# remaining stack, allowing the container restart policy to recover cleanly.
wait -n "${CHILD_PIDS[@]}"
log "ERROR: a critical process exited"
exit 1

