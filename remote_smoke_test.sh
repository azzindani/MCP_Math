#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MCP_Math (math-mcp-server) — remote smoke test.
#
# NOT part of pytest / CI (see CLAUDE.md §12 "Remote smoke tests"). pytest
# stays offline-only per STANDARDS.md; this script is the separate,
# manual/on-demand check that actually exercises the deployed HTTP endpoint:
# real auth enforcement + real handwritten-prompt-style tool calls with real
# data, against the real public domain — not just /health.
#
# Usage:
#   ./remote_smoke_test.sh                        # reads MATH_API_KEY from .env
#   MATH_API_KEY=sk-... ./remote_smoke_test.sh     # or pass it directly
#   DOMAIN=http://localhost:8765 ./remote_smoke_test.sh   # test a different target
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="${DOMAIN:-https://math.casava.space}"
if [ -f .env ]; then
  set -a; source .env; set +a
fi
KEY="${MATH_API_KEY:?Set MATH_API_KEY (env var or .env file) before running}"

pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1"; exit 1; }

echo "Target: $DOMAIN"
echo
echo "== auth enforcement =="

code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$DOMAIN/mcp" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}')
[ "$code" = "401" ] && pass "no token -> 401" || fail "no token -> expected 401, got $code"

SID=$(curl -s -i -X POST "$DOMAIN/mcp" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}' \
  | grep -i mcp-session-id | tr -d '\r' | awk '{print $2}')
[ -n "$SID" ] && pass "valid token -> session established" || fail "valid token -> no session id returned"

curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"notifications/initialized"}' > /dev/null

echo
echo '== prompt: "what is 12 * 7 + sqrt(81)?" -> calculate =='
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"calculate","arguments":{"expression":"12*7+sqrt(81)"}}}')
echo "$RESULT" | grep -q '"result":93' && pass "calculate(12*7+sqrt(81)) = 93" || fail "unexpected result: $RESULT"

echo
echo '== prompt: "solve x^2 - 9 = 0" -> solve =='
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"solve","arguments":{"equation":"x**2 - 9","variable":"x"}}}')
echo "$RESULT" | grep -q '"-3"' && echo "$RESULT" | grep -q '"3"' \
  && pass 'solve(x^2 - 9) = {-3, 3}' || fail "unexpected result: $RESULT"

echo
echo '== prompt: "how many kilometers is 10 miles?" -> convert_units =='
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"convert_units","arguments":{"value":10,"from_unit":"mile","to_unit":"kilometer"}}}')
echo "$RESULT" | grep -q '16.09344' && pass "convert_units(10 mile -> km) = 16.09344" || fail "unexpected result: $RESULT"

echo
echo "ALL CHECKS PASSED against $DOMAIN"
