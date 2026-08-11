#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${1:-$HOME/thesis_project}"

echo "=== Building federation_network Docker images for network topology plugin ==="

cd "$PROJECT_DIR"

echo "[federation_network-slips]"
docker compose -f docker-compose.yml build slips-1 2>&1 | tail -3
docker tag scl-custom_challenge-slips federation_network-slips:latest

echo "[federation_network-service]"
docker build -f service/Dockerfile -t federation_network-service:latest . 2>&1 | tail -3

echo ""
echo "=== All federation_network images ==="
docker images --format '{{.Repository}}:{{.Tag}}' | grep '^federation_network-'
