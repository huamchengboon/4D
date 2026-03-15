#!/usr/bin/env bash
# Run this on the server (mac-mini) from the zero project root: /Users/chengboon/Docker/zero
# Usage: ./4d/deploy-on-server.sh
# Or: bash 4d/deploy-on-server.sh
set -e
ZERO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ZERO_ROOT"
FOURD_DIR="$ZERO_ROOT/4d"
REPO_URL="${4D_REPO_URL:-https://github.com/huamchengboon/4D.git}"

if [[ ! -d "$FOURD_DIR/.git" ]]; then
  echo "Cloning 4D repo into $FOURD_DIR ..."
  git clone "$REPO_URL" "$FOURD_DIR"
else
  echo "Pulling latest in $FOURD_DIR ..."
  (cd "$FOURD_DIR" && git pull)
fi

mkdir -p "$FOURD_DIR/data"
if [[ ! -f "$FOURD_DIR/data/4d_history.csv" ]]; then
  echo "Note: $FOURD_DIR/data/4d_history.csv not found. Backend will run but may have no history data."
fi

echo "Building and starting 4d-backend and 4d-frontend ..."
docker compose -f docker-compose.yml -f 4d/4d-compose.zero.yml build 4d-backend 4d-frontend
docker compose -f docker-compose.yml -f 4d/4d-compose.zero.yml up -d 4d-backend 4d-frontend
echo "Done. 4d should be available at https://4d.chengboon.com (after Dockflare picks up the new container)."
