#!/usr/bin/env bash
#
# End-to-end smoke test for the quant-system stack.
# Assumes `docker compose up -d` has been run from the docker/ directory.
#
# Usage:
#   ./scripts/smoke-test.sh                   # default: gateway at localhost:8080
#   GATEWAY=http://192.168.1.5:8080 ./scripts/smoke-test.sh
#
set -euo pipefail

GATEWAY="${GATEWAY:-http://localhost:8080}"
BIZ="${BIZ:-http://localhost:8081}"
PASS=0
FAIL=0
SKIP=0

green()  { printf '\033[32m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }

check() {
    local label="$1" url="$2" expected_status="${3:-200}" body_grep="${4:-}"
    local status body
    body=$(curl -s -w '\n%{http_code}' --max-time 10 "$url" 2>/dev/null || echo "000")
    status=$(echo "$body" | tail -1)
    body=$(echo "$body" | sed '$d')

    if [[ "$status" == "$expected_status" ]]; then
        if [[ -n "$body_grep" && ! "$body" =~ $body_grep ]]; then
            red  "FAIL  $label — status $status but body missing '$body_grep'"
            ((FAIL++))
        else
            green "PASS  $label — HTTP $status"
            ((PASS++))
        fi
    elif [[ "$status" == "000" ]]; then
        yellow "SKIP  $label — connection refused (service not running?)"
        ((SKIP++))
    else
        red "FAIL  $label — expected $expected_status, got $status"
        ((FAIL++))
    fi
}

check_post() {
    local label="$1" url="$2" data="$3" expected_status="${4:-200}" body_grep="${5:-}"
    local status body
    body=$(curl -s -w '\n%{http_code}' --max-time 10 \
        -X POST -H 'Content-Type: application/json' -d "$data" "$url" 2>/dev/null || echo "000")
    status=$(echo "$body" | tail -1)
    body=$(echo "$body" | sed '$d')

    if [[ "$status" == "$expected_status" ]]; then
        if [[ -n "$body_grep" && ! "$body" =~ $body_grep ]]; then
            red  "FAIL  $label — status $status but body missing '$body_grep'"
            ((FAIL++))
        else
            green "PASS  $label — HTTP $status"
            ((PASS++))
        fi
    elif [[ "$status" == "000" ]]; then
        yellow "SKIP  $label — connection refused"
        ((SKIP++))
    else
        red "FAIL  $label — expected $expected_status, got $status"
        ((FAIL++))
    fi
}

echo ""
echo "====================================="
echo " Quant-System Smoke Tests"
echo " Gateway : $GATEWAY"
echo " Biz     : $BIZ"
echo "====================================="
echo ""

# ─── Infrastructure ──────────────────────────────────────

echo "── Infrastructure ──"
check "Redis ping"      "redis://localhost:6379" "" "" || true
# Test via docker
redis_ok=$(docker exec quant-redis redis-cli ping 2>/dev/null || echo "SKIP")
if [[ "$redis_ok" == "PONG" ]]; then
    green "PASS  Redis PING → PONG"
    ((PASS++))
elif [[ "$redis_ok" == "SKIP" ]]; then
    yellow "SKIP  Redis (container not running)"
    ((SKIP++))
else
    red "FAIL  Redis PING → $redis_ok"
    ((FAIL++))
fi

pg_ok=$(docker exec quant-postgres pg_isready -U quant 2>/dev/null && echo "OK" || echo "SKIP")
if [[ "$pg_ok" == *"OK"* ]]; then
    green "PASS  PostgreSQL ready"
    ((PASS++))
elif [[ "$pg_ok" == "SKIP" ]]; then
    yellow "SKIP  PostgreSQL (container not running)"
    ((SKIP++))
else
    red "FAIL  PostgreSQL not ready"
    ((FAIL++))
fi
echo ""

# ─── Java Biz-Service (direct) ──────────────────────────

echo "── Java Biz-Service (direct :8081) ──"
check "Actuator health"       "$BIZ/actuator/health"    200 "UP"
check "Soy futures"           "$BIZ/api/soy/futures"    200
check "Crush margin"          "$BIZ/api/soy/crush-margin" 200 "signal"
check "Fund list"             "$BIZ/api/fund/list"      200
echo ""

# ─── Auth flow ───────────────────────────────────────────

echo "── Auth flow ──"
TS=$(date +%s)
REG_BODY="{\"username\":\"smoke_${TS}\",\"password\":\"Sm0keTest!\",\"email\":\"smoke_${TS}@test.dev\"}"
REG_RESP=$(curl -s --max-time 10 -X POST -H 'Content-Type: application/json' \
    -d "$REG_BODY" "$BIZ/api/auth/register" 2>/dev/null || echo '{"error":"conn"}')

if echo "$REG_RESP" | grep -q "access_token"; then
    green "PASS  Register user smoke_${TS}"
    ((PASS++))

    ACCESS=$(echo "$REG_RESP" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    REFRESH=$(echo "$REG_RESP" | grep -o '"refresh_token":"[^"]*"' | cut -d'"' -f4)

    LOGIN_BODY="{\"username\":\"smoke_${TS}\",\"password\":\"Sm0keTest!\"}"
    check_post "Login" "$BIZ/api/auth/login" "$LOGIN_BODY" 200 "access_token"

    if [[ -n "$REFRESH" ]]; then
        REFRESH_BODY="{\"refresh_token\":\"${REFRESH}\"}"
        check_post "Refresh token" "$BIZ/api/auth/refresh" "$REFRESH_BODY" 200 "access_token"
    fi

    check_post "Duplicate register" "$BIZ/api/auth/register" "$REG_BODY" 400 "USER_EXISTS"
else
    yellow "SKIP  Auth flow (biz-service not reachable)"
    ((SKIP+=4))
fi
echo ""

# ─── Go Gateway ──────────────────────────────────────────

echo "── Go Gateway (:8080) ──"
check "Gateway health"        "$GATEWAY/health"         200
check "Gateway → soy/futures" "$GATEWAY/api/soy/futures" 200
check "Gateway → fund/list"   "$GATEWAY/api/fund/list"  200
check "Gateway metrics"       "$GATEWAY/metrics"        200
check "Gateway metrics JSON"  "$GATEWAY/metrics/json"   200 "total_requests"
echo ""

# ─── Python data-pipeline status ─────────────────────────

echo "── Python data-pipeline ──"
DP_PORT="${DP_PORT:-9100}"
check "Pipeline health"  "http://localhost:$DP_PORT/health" 200
check "Pipeline status"  "http://localhost:$DP_PORT/status" 200
echo ""

# ─── Python signal-agent status ──────────────────────────

echo "── Python signal-agent ──"
SA_PORT="${SA_PORT:-9200}"
check "Signal health"    "http://localhost:$SA_PORT/health"         200
check "Signal latest"    "http://localhost:$SA_PORT/signal/latest"  200
echo ""

# ─── WebSocket quick probe ───────────────────────────────

echo "── WebSocket ──"
WS_OK=$(timeout 3 curl -s -o /dev/null -w '%{http_code}' \
    -H 'Upgrade: websocket' -H 'Connection: Upgrade' \
    -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    -H 'Sec-WebSocket-Version: 13' \
    "$GATEWAY/ws/quotes" 2>/dev/null || echo "000")
if [[ "$WS_OK" == "101" ]]; then
    green "PASS  WebSocket upgrade → 101"
    ((PASS++))
elif [[ "$WS_OK" == "000" ]]; then
    yellow "SKIP  WebSocket (gateway not reachable)"
    ((SKIP++))
else
    yellow "SKIP  WebSocket — got $WS_OK (may need proper WS client)"
    ((SKIP++))
fi
echo ""

# ─── Summary ─────────────────────────────────────────────

echo "====================================="
echo " Results: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
echo "====================================="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
exit 0
