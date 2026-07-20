#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
THESIS_DIR="${1:-$HOME/thesis_project}"

echo "=== Building thesis Docker images for network topology plugin ==="

cd "$THESIS_DIR"

echo "[thesis-slips]"
docker compose -f docker-compose.yml build slips-1 2>&1 | tail -3
docker tag scl-custom_challenge-slips thesis-slips:latest
docker tag scl-custom_challenge-slips-slips_base thesis-slips-base:latest

echo "[thesis-attacker]"
docker compose -f docker-compose.yml build attacker 2>&1 | tail -3
docker tag scl-custom_challenge-attacker thesis-attacker:latest

echo "[thesis-pivot]"
docker compose -f docker-compose.yml build connect 2>&1 | tail -3
docker tag scl-custom_challenge-connect thesis-pivot:latest

echo "[thesis-ftp]"
docker compose -f docker-compose.yml build ubuntu-1 2>&1 | tail -3
docker tag scl-custom_challenge-ftp thesis-ftp:latest

echo "[thesis-snmp]"
docker compose -f docker-compose.yml build ubuntu-2 2>&1 | tail -3
docker tag scl-custom_challenge-snmp thesis-snmp:latest

echo ""
echo "=== All thesis images tagged ==="
docker images --format '{{.Repository}}:{{.Tag}}' | grep '^thesis-'
