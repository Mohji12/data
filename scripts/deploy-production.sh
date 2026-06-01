#!/usr/bin/env bash
# Pull latest from GitHub and restart services on the production API server.
# Default layout: repo cloned at /home/ubuntu/data (Mohji12/data).
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/ubuntu/data}"
BRANCH="${BRANCH:-main}"
BUILD_FRONTEND="${BUILD_FRONTEND:-1}"
FRONTEND_DIR="${FRONTEND_DIR:-$APP_ROOT/critical-pulse-hub-main}"
WEB_ROOT="${WEB_ROOT:-/var/www/criticalcare}"
API_SERVICE="${API_SERVICE:-criticalcare-api}"

echo "==> Deploy from $APP_ROOT (branch $BRANCH)"
cd "$APP_ROOT"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo "==> Backend"
cd "$APP_ROOT/backend"
if [[ -d venv ]]; then
  source venv/bin/activate
elif [[ -d .venv ]]; then
  source .venv/bin/activate
else
  python3 -m venv venv
  source venv/bin/activate
fi
pip install -r requirements.txt -q
sudo systemctl restart "$API_SERVICE"
sudo systemctl status "$API_SERVICE" --no-pager || true

if [[ "$BUILD_FRONTEND" == "1" && -d "$FRONTEND_DIR" ]]; then
  echo "==> Frontend ($FRONTEND_DIR)"
  cd "$FRONTEND_DIR"
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
  npm run build
  if [[ -d "$WEB_ROOT" ]]; then
    sudo mkdir -p "$WEB_ROOT"
    sudo rm -rf "${WEB_ROOT:?}"/*
    sudo cp -r dist/* "$WEB_ROOT"/
    sudo chown -R www-data:www-data "$WEB_ROOT" 2>/dev/null || true
  else
    echo "WEB_ROOT $WEB_ROOT not found — skip static copy (build is in $FRONTEND_DIR/dist)"
  fi
fi

echo "==> Health check"
curl -sf "http://127.0.0.1:8000/health" >/dev/null && echo "API OK" || echo "API health check failed — check journalctl -u $API_SERVICE"

echo "Deploy finished. Latest commit:"
git -C "$APP_ROOT" log -1 --oneline
