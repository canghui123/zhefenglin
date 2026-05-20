#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
if [ -z "$BASE_URL" ]; then
  if [ -f .env ]; then
    DOMAIN_VALUE="$(grep -E '^DOMAIN=' .env | tail -1 | cut -d= -f2- || true)"
    if [ -n "$DOMAIN_VALUE" ]; then
      BASE_URL="https://${DOMAIN_VALUE}"
    fi
  fi
fi
BASE_URL="${BASE_URL:-https://zhefenglin.com}"

if docker compose ps >/dev/null 2>&1; then
  COMPOSE=(docker compose)
else
  COMPOSE=(sudo docker compose)
fi

echo "== compose services =="
"${COMPOSE[@]}" ps

echo "== backend import =="
"${COMPOSE[@]}" exec -T backend python -c 'from main import app; print("backend import ok")'

echo "== health =="
curl -k -fsS "${BASE_URL}/api/health"
echo

echo "== frontend =="
curl -k -fsSI "${BASE_URL}/asset-pricing" | sed -n '1,12p'

echo "smoke check ok: ${BASE_URL}"
