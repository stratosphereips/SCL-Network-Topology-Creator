#!/usr/bin/env bash
# Build the federation_network-* runtime images from this plugin's
# federation/ sources — same steps as POST /api/images/build.
#   ./build-images.sh [slips_branch_or_sha]
# SLIPS is built from SLIPS_REPO at one exact commit with the branch's own
# docker/Dockerfile; the federation layer goes on top.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/federation"
SLIPS_REPO="${SLIPS_REPO:-https://github.com/stratosphereips/StratosphereLinuxIPS.git}"
REF="${1:-${SLIPS_BRANCH:-fl_module_jan_rebased}}"

if [[ "$REF" =~ ^[0-9a-f]{40}$ ]]; then
  SHA="$REF"
else
  SHA="$(git ls-remote "$SLIPS_REPO" "refs/heads/$REF" "refs/tags/$REF" | awk 'NR==1{print $1}')"
fi
[[ -n "$SHA" ]] || { echo "cannot resolve $REF in $SLIPS_REPO" >&2; exit 1; }
BASE="federation_network-slips-base:${SHA:0:12}"

echo "=== federation_network-slips: $REF @ $SHA ==="
if ! docker image inspect "$BASE" >/dev/null 2>&1; then
  docker build -f docker/Dockerfile --build-arg "SLIPS_GIT_REF=$SHA" -t "$BASE" "$SLIPS_REPO#$SHA"
fi
docker build -f "$SRC/slips/Dockerfile" \
  --build-arg "BASE_IMAGE=$BASE" --build-arg "SLIPS_COMMIT=$SHA" --build-arg "SLIPS_BRANCH=$REF" \
  -t scl-custom_challenge-slips "$SRC"
docker tag scl-custom_challenge-slips federation_network-slips:latest

echo "=== federation_network-service ==="
docker build -f "$SRC/service/Dockerfile" -t federation_network-service:latest "$SRC"

echo "=== federation_network-attacker ==="
docker build -f "$SCRIPT_DIR/attacker/Dockerfile" -t federation_network-attacker:latest "$SCRIPT_DIR/attacker"

docker images --format '{{.Repository}}:{{.Tag}}' | grep '^federation_network-'
