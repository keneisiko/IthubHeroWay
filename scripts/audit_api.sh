#!/usr/bin/env bash
# Smoke-test all Hero Path API endpoints used by the frontend.
# Usage:
#   export API_BASE=http://localhost:8000
#   export API_LOGIN=your@email
#   export API_PASSWORD=secret
#   ./scripts/audit_api.sh

set -euo pipefail

BASE="${API_BASE:-http://localhost:8000}"
LOGIN="${API_LOGIN:-}"
PASSWORD="${API_PASSWORD:-}"

if [[ -z "$LOGIN" || -z "$PASSWORD" ]]; then
  echo "Set API_LOGIN and API_PASSWORD environment variables." >&2
  exit 1
fi

check() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local extra="${4:-}"
  local url="${BASE}${path}"
  if [[ "$method" == "GET" ]]; then
    code=$(curl -s -o /tmp/audit_body.json -w "%{http_code}" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      $extra "$url")
  else
    code=$(curl -s -o /tmp/audit_body.json -w "%{http_code}" \
      -X "$method" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      -d "$body" \
      $extra "$url")
  fi
  echo "[$code] $method $path"
  if command -v jq >/dev/null 2>&1; then
    head -c 200 /tmp/audit_body.json | jq -c . 2>/dev/null || head -c 120 /tmp/audit_body.json
  else
    head -c 120 /tmp/audit_body.json
  fi
  echo
}

echo "== Login =="
LOGIN_RESP=$(curl -s -X POST "${BASE}/api/v1/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"login\":\"${LOGIN}\",\"password\":\"${PASSWORD}\"}")
TOKEN=$(echo "$LOGIN_RESP" | python -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null || true)
if [[ -z "$TOKEN" ]]; then
  echo "Login failed: $LOGIN_RESP" >&2
  exit 1
fi
echo "Token acquired."

echo
echo "== Dashboard & profile =="
check GET "/api/v1/dashboard/"
check GET "/api/v1/profile/me/"
check GET "/api/v1/profile/me/characteristics/"
check GET "/api/v1/rating/me/"

echo
echo "== Leaderboard & squads =="
check GET "/api/v1/leaderboard/agents/?page=1&page_size=20"
check GET "/api/v1/leaderboard/agents/?page=1&page_size=20&track=dev-backend"
check GET "/api/v1/leaderboard/agents/?page=1&page_size=20&search=demo"
check GET "/api/v1/squads/me/"
check GET "/api/v1/squads/"
check GET "/api/v1/squads/leaderboard/?limit=10"

echo
echo "== Quests & shop =="
check GET "/api/v1/quests/active/"
check GET "/api/v1/quests/my-progress/?completed=false"
check GET "/api/v1/quests/rewards/history/"
check GET "/api/v1/shop/items/"
check GET "/api/v1/shop/my-purchases/"

echo
echo "== Badges & social =="
check GET "/api/v1/badges/my/"
check GET "/api/v1/badges/"

echo
echo "Done."
