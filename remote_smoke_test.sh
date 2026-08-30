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
# Read the key out of .env without executing it. `source` runs every line of
# the file, so a line that is not a KEY=VALUE assignment is a command; that has
# already turned a stray summary line into a file named after a secret. A plain
# read of one assignment cannot do that.
if [ -z "${MATH_API_KEY:-}" ] && [ -f .env ]; then
  MATH_API_KEY=$(sed -n 's/^[[:space:]]*MATH_API_KEY[[:space:]]*=[[:space:]]*//p' .env | tail -n1 | tr -d '\042\047\r')
fi
KEY="${MATH_API_KEY:?Set MATH_API_KEY (env var or .env file) before running}"

# Every MCP response is an SSE frame whose result.content[0].text is itself a
# JSON *string*, so each quote inside it arrives escaped and each colon gains a
# space: a grep for '"result":93' cannot match '\"result\": 93'. Decode the
# inner document once and assert against that. The envelope greps below used to
# match because responses also carried structuredContent; moving to the
# official MCP SDK dropped that field, and since the calls themselves still
# succeeded, every assertion in this file silently stopped checking anything.
mcp_text() {
  python3 -c '
import json, sys
raw = sys.stdin.read()
for line in raw.splitlines():
    if line.startswith("data:"):
        payload = json.loads(line[5:])
        content = payload.get("result", {}).get("content", [])
        print(content[0]["text"] if content else json.dumps(payload))
        break
else:
    print(raw)
'
}

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
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"calculate","arguments":{"expression":"12*7+sqrt(81)"}}}' | mcp_text)
echo "$RESULT" | grep -q '"result": 93' && pass "calculate(12*7+sqrt(81)) = 93" || fail "unexpected result: $RESULT"

echo
echo '== prompt: "solve x^2 - 9 = 0" -> solve =='
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"solve","arguments":{"equation":"x**2 - 9","variable":"x"}}}' | mcp_text)
# Roots are JSON NUMBERS, not quoted strings. This asserted '"-3"' and '"3"'
# until a698044 made solve() stop returning its roots as text -- so the check
# that should have proved the fix was the last thing still requiring the
# defect, and it is the reason that commit's CI went red. Two unit tests in
# test_human_notation_parses.py had locked the same string form in place and
# were updated with the fix; this one was missed because pytest never runs it.
# Roots are JSON NUMBERS, not quoted strings. This asserted '"-3"' and '"3"'
# until a698044 made solve() stop returning its roots as text -- so the check
# that should have proved the fix was the last thing still requiring the
# defect, and it is why that commit's CI went red. Two unit tests in
# test_human_notation_parses.py had locked the same string form in place and
# were updated with the fix; this one was missed because pytest never runs it.
#
# Whitespace is stripped and the whole array is matched at once, rather than
# grepping for each root: the payload is pretty-printed across several lines,
# so a per-line pattern cannot see the brackets, and `"3"` on its own would
# also match "13" or a quoted 3 somewhere else in the response.
echo "$RESULT" | tr -d ' \n\r' | grep -q '"result":\[-3,3\]' \
  && pass 'solve(x^2 - 9) = [-3, 3], as numbers' || fail "unexpected result: $RESULT"

echo
echo '== prompt: "how many kilometers is 10 miles?" -> convert_units =='
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"convert_units","arguments":{"value":10,"from_unit":"mile","to_unit":"kilometer"}}}' | mcp_text)
echo "$RESULT" | grep -q '16.09344' && pass "convert_units(10 mile -> km) = 16.09344" || fail "unexpected result: $RESULT"

echo
echo '== prompt: "simplify (x^2 - 1)/(x - 1)" -> simplify =='
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"simplify","arguments":{"expression":"(x**2 - 1)/(x - 1)"}}}' | mcp_text)
echo "$RESULT" | grep -q '"result": "x + 1"' && pass "simplify((x^2-1)/(x-1)) = x + 1" || fail "unexpected result: $RESULT"

echo
echo '== prompt: "what is the derivative of x^3 + 2x with respect to x?" -> diff =='
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"diff","arguments":{"expression":"x**3 + 2*x","variable":"x","order":1}}}' | mcp_text)
echo "$RESULT" | grep -q '"result": "3\*x\*\*2 + 2"' && pass "diff(x^3 + 2x) = 3x^2 + 2" || fail "unexpected result: $RESULT"

echo
echo '== prompt: "integrate 2x from 0 to 5" -> integrate =='
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"integrate","arguments":{"expression":"2*x","variable":"x","lower":"0","upper":"5"}}}' | mcp_text)
echo "$RESULT" | grep -q '"result": "25"' && pass "integrate(2x, 0, 5) = 25" || fail "unexpected result: $RESULT"

echo
echo '== prompt: "give me descriptive stats for this dataset" -> describe (real generated dataset) =='
DATASET=$(python3 -c "
import random
random.seed(11)
print([round(random.gauss(50, 10), 2) for _ in range(40)])
")
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":9,\"method\":\"tools/call\",\"params\":{\"name\":\"describe\",\"arguments\":{\"dataset\":$DATASET}}}" | mcp_text)
echo "$RESULT" | grep -q '"count": 40' && pass "describe(40-point generated dataset) computed real stats" || fail "unexpected result: $RESULT"

echo
echo '== prompt: "evaluate a/b + c where a=10, b=4, c=2" -> eval_latex =='
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"eval_latex","arguments":{"formula":"\\frac{a}{b} + c","variables":{"a":10,"b":4,"c":2}}}}' | mcp_text)
echo "$RESULT" | grep -q '"result": 4.5' && pass "eval_latex(a/b + c, a=10,b=4,c=2) = 4.5" || fail "unexpected result: $RESULT"

echo
echo "== security: sympify() injection payload is rejected, not executed =="
RESULT=$(curl -s -X POST "$DOMAIN/mcp" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $KEY" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"calculate","arguments":{"expression":"__import__(\"os\").system(\"echo PWNED\")"}}}' | mcp_text)
echo "$RESULT" | grep -Eq '"success":[[:space:]]*false' && pass "dunder-import payload rejected (success:false)" || fail "expected rejection, got: $RESULT"
echo "$RESULT" | grep -q "must not contain" && pass "rejected specifically by the '__' guard in safe_sympify(), not a generic parse failure" || fail "expected the safe_sympify '__' guard message, got: $RESULT"

echo
echo "ALL 8 TOOLS + security regression PASSED against $DOMAIN"
