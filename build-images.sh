#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${1:-$HOME/thesis_project}"

echo "=== Building federation_network Docker images for network topology plugin ==="

cd "$PROJECT_DIR"

echo "[federation_network-slips]"
docker compose -f docker-compose.yml build slips-1 2>&1 | tail -3
docker tag scl-custom_challenge-slips federation_network-slips:latest

echo "[federation_network-attacker]"
docker compose -f docker-compose.yml build attacker 2>&1 | tail -3
docker tag scl-custom_challenge-attacker federation_network-attacker:latest

echo "[federation_network-pivot]"
docker compose -f docker-compose.yml build connect 2>&1 | tail -3
docker tag scl-custom_challenge-connect federation_network-pivot:latest

echo "[federation_network-ftp]"
docker compose -f docker-compose.yml build ubuntu-1 2>&1 | tail -3
docker tag scl-custom_challenge-ftp federation_network-ftp:latest

echo "[federation_network-snmp]"
docker compose -f docker-compose.yml build ubuntu-2 2>&1 | tail -3
docker tag scl-custom_challenge-snmp federation_network-snmp:latest

echo ""
echo "=== All federation_network images tagged ==="
docker images --format '{{.Repository}}:{{.Tag}}' | grep '^federation_network-'
