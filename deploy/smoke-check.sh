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

echo "== alembic migration =="
CURRENT_REVISION="$("${COMPOSE[@]}" exec -T backend alembic current | awk '/^[0-9]/ {print $1}' | tail -1)"
HEAD_REVISION="$("${COMPOSE[@]}" exec -T backend alembic heads | awk '/^[0-9]/ {print $1}' | tail -1)"
if [ -z "$CURRENT_REVISION" ] || [ -z "$HEAD_REVISION" ] || [ "$CURRENT_REVISION" != "$HEAD_REVISION" ]; then
  echo "alembic migration is not at head: current=${CURRENT_REVISION:-unknown}, head=${HEAD_REVISION:-unknown}" >&2
  echo "run: docker compose run --rm backend alembic upgrade head" >&2
  exit 1
fi
echo "alembic current=head (${CURRENT_REVISION})"

echo "== health =="
curl -k -fsS "${BASE_URL}/api/health"
echo

echo "== frontend =="
curl -k -fsSI "${BASE_URL}/asset-pricing" | sed -n '1,12p'

echo "== env drift check =="
# B4: 主动验证 DB / S3 / JWT / CHE300 / 存储 / CORS 配置漂移
# 任何一项失败 smoke-check 会非 0 退出。这就是 2026-05-30 一天内撞 3 次
# 配置漂移(DB_PASSWORD / S3 / CHE300)之后加的最后一道关。
"${COMPOSE[@]}" exec -T backend python3 scripts/env_drift_check.py

echo "smoke check ok: ${BASE_URL}"
