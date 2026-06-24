#!/usr/bin/env bash
# Full backend audit: infra, env, management commands, API GET+POST smoke.
# Usage:
#   export API_BASE=http://localhost:8000
#   export API_LOGIN=your@email      # optional if JWT fallback works
#   export API_PASSWORD=secret
#   ./scripts/audit_backend.sh

set -euo pipefail

BASE="${API_BASE:-http://localhost:8000}"
LOGIN="${API_LOGIN:-}"
PASSWORD="${API_PASSWORD:-}"
FAILURES=0
WARNINGS=0

pass() { echo "  OK  $1"; }
fail() { echo "  FAIL $1"; FAILURES=$((FAILURES + 1)); }
warn() { echo "  WARN $1"; WARNINGS=$((WARNINGS + 1)); }

section() { echo; echo "== $1 =="; }

curl_json() {
  local method="$1" url="$2" body="${3:-}" auth="${4:-}"
  local args=(-s -w "\n%{http_code}" -H "Content-Type: application/json")
  [[ -n "$auth" ]] && args+=(-H "Authorization: Bearer $auth")
  if [[ "$method" == "GET" ]]; then
    curl "${args[@]}" "$url"
  else
    curl "${args[@]}" -X "$method" -d "$body" "$url"
  fi
}

section "Docker containers"
if command -v docker >/dev/null 2>&1; then
  if docker compose ps 2>/dev/null | grep -q "Up"; then
    pass "docker compose services running"
  else
    warn "docker compose not fully up (continuing with HTTP checks)"
  fi
else
  warn "docker not available"
fi

section "Infra endpoints"
for path in /health/ /ready/; do
  resp=$(curl_json GET "${BASE}${path}")
  code=$(echo "$resp" | tail -n1)
  body=$(echo "$resp" | sed '$d')
  if [[ "$code" == "200" ]]; then
    pass "GET ${path} [$code] $(echo "$body" | head -c 80)"
  else
    fail "GET ${path} [$code]"
  fi
done

metrics_code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/metrics/")
if [[ "$metrics_code" == "200" ]]; then pass "GET /metrics/ [200]"; else fail "GET /metrics/ [$metrics_code]"; fi

schema_code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/schema/")
if [[ "$schema_code" == "200" ]]; then pass "GET /schema/ [200]"; else fail "GET /schema/ [$schema_code]"; fi

section "Environment variables (presence only)"
ENV_VARS=(DATABASE_URL REDIS_URL SECRET_KEY CELERY_BROKER_URL HIK_DATA_MODE LXP_VERIFY_URL LXP_API_TOKEN HIK_HOST TELEGRAM_BOT_TOKEN)
for v in "${ENV_VARS[@]}"; do
  if [[ -n "${!v:-}" ]]; then pass "$v set"; else warn "$v not set (may be ok in dev)"; fi
done

section "Management commands (--help)"
MGMT_CMDS=(import_lxp_students backfill_lxp_user_ids pull_lxp_performance sync_hik_events pull_hik_attendance verify_quests test_alert seed_demo_data)
for cmd in "${MGMT_CMDS[@]}"; do
  if docker compose exec -T web python manage.py "$cmd" --help >/dev/null 2>&1; then
    pass "manage.py $cmd"
  elif python manage.py "$cmd" --help >/dev/null 2>&1; then
    pass "manage.py $cmd (local)"
  else
    warn "manage.py $cmd unavailable"
  fi
done

section "Auth token"
TOKEN=""
if [[ -n "$LOGIN" && -n "$PASSWORD" ]]; then
  login_resp=$(curl -s -X POST "${BASE}/api/v1/auth/login/" \
    -H "Content-Type: application/json" \
    -d "{\"login\":\"${LOGIN}\",\"password\":\"${PASSWORD}\"}" || true)
  TOKEN=$(echo "$login_resp" | python -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null || true)
  if [[ -n "$TOKEN" ]]; then
    pass "LXP login token acquired"
  else
    warn "LXP login failed; trying JWT create"
  fi
fi

if [[ -z "$TOKEN" && -n "$LOGIN" && -n "$PASSWORD" ]]; then
  jwt_resp=$(curl -s -X POST "${BASE}/api/v1/auth/jwt/create/" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${LOGIN}\",\"password\":\"${PASSWORD}\"}" || true)
  TOKEN=$(echo "$jwt_resp" | python -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null || true)
  [[ -n "$TOKEN" ]] && pass "JWT create token acquired" || fail "Could not obtain auth token"
fi

if [[ -z "$TOKEN" ]]; then
  warn "No API_LOGIN/API_PASSWORD — skipping authenticated API checks"
fi

api_get() {
  local path="$1"
  local resp code
  resp=$(curl_json GET "${BASE}${path}" "" "$TOKEN")
  code=$(echo "$resp" | tail -n1)
  if [[ "$code" =~ ^2 ]]; then pass "GET $path [$code]"; else fail "GET $path [$code]"; fi
}

api_post() {
  local path="$1" body="$2"
  local expect="${3:-2}"
  local resp code
  resp=$(curl_json POST "${BASE}${path}" "$body" "$TOKEN")
  code=$(echo "$resp" | tail -n1)
  if [[ "$code" =~ ^${expect} ]]; then pass "POST $path [$code]"; else fail "POST $path [$code]"; fi
}

if [[ -n "$TOKEN" ]]; then
  section "API GET smoke"
  GET_PATHS=(
    /api/v1/dashboard/
    /api/v1/profile/me/
    /api/v1/profile/me/characteristics/
    /api/v1/rating/me/
    /api/v1/rating/history/
    /api/v1/leaderboard/agents/?page=1&page_size=20
    /api/v1/squads/me/
    /api/v1/squads/
    /api/v1/squads/leaderboard/?limit=10
    /api/v1/quests/active/
    /api/v1/quests/my-progress/?completed=false
    /api/v1/quests/rewards/history/
    /api/v1/shop/items/
    /api/v1/shop/my-purchases/
    /api/v1/badges/my/
    /api/v1/badges/
  )
  for p in "${GET_PATHS[@]}"; do api_get "$p"; done

  section "API POST smoke (non-destructive where possible)"
  api_post /api/v1/auth/jwt/refresh/ "{\"refresh\":\"invalid\"}" "4"
  api_post /api/v1/social/respects/ "{\"to_username\":\"nonexistent_user_xyz\"}" "4"
  api_post /api/v1/social/duels/ "{\"opponent_username\":\"nonexistent_user_xyz\"}" "4"
  api_post /api/v1/social/mentorships/ "{\"mentee_username\":\"nonexistent_user_xyz\"}" "4"
fi

section "Summary"
echo "Failures: $FAILURES  Warnings: $WARNINGS"
if [[ "$FAILURES" -gt 0 ]]; then exit 1; fi
echo "Backend audit passed (critical checks)."
exit 0
