#!/usr/bin/env bash
# Healthcheck for the Leosac host stack: all three services answering + both
# boot markers present (mirrors erpnext-healthcheck.sh).
set -eu

test -f /tmp/leosac-stack-ready
test -f /tmp/leosac-seed-ready

pg_isready -q
nc -w1 -z 127.0.0.1 8888
curl -fsS --max-time 5 -o /dev/null http://127.0.0.1/
