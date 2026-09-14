#!/usr/bin/env bash
set -eu

test -f /tmp/greedy-stack-ready
test -f /tmp/greedy-seed-ready
mysqladmin ping --silent
test "$(mysql -N -ugreedy_cars -padminAdmin greedy_cars_db \
    -e 'SELECT COUNT(*) FROM vehiculo' 2>/dev/null)" -ge 4
curl -sS --max-time 3 -o /dev/null \
    http://127.0.0.1:9000/greedy_cars/api
for url in \
    http://127.0.0.1:8080/greedy_institucional/ \
    http://127.0.0.1:8081/gredy_cars_client/ \
    http://127.0.0.1/gredy_cars_client/; do
    curl -fsS --max-time 3 -o /dev/null "$url"
done

