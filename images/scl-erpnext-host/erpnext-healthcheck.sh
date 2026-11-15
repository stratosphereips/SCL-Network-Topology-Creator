#!/usr/bin/env bash
# Healthcheck for the ERPNext host (mirrors hospital-healthcheck.sh).
# Healthy = stack supervisor finished provisioning + MariaDB up + Redis up +
# gunicorn answering Frappe's ping endpoint through both :8000 and the nginx
# front door :80. The start-period in the Dockerfile gives the first-boot site
# setup (~3-5 min: new-site + install-app erpnext + seed) room before this runs.
set -eu

test -f /tmp/erp-stack-ready
test -f /tmp/erp-seed-ready
mysqladmin ping --silent
redis-cli -p 6379 ping | grep -q PONG
# Frappe ping on its own port and through the nginx front door.
curl -fsS --max-time 6 -o /dev/null http://127.0.0.1:8000/api/method/ping
curl -fsS --max-time 6 -o /dev/null http://127.0.0.1/api/method/ping
