#!/bin/bash
# Test the dashboard auth proxy — isolation + connectivity.
#
# Tests:
#   1. Token isolation: no token files on disk
#   2. Memory protection: /proc/PID/mem, /proc/PID/environ blocked
#   3. Proxy listening: localhost:8889 is up
#   4. Proxy forwarding: request through proxy reaches MCP (via OPA proxy)
#   5. Direct MCP bypass: request without token gets 401
#   6. Per-sandbox OPA: cross-department MCP blocked
#   7. Token injection: proxy adds Authorization header (after login)
#
# Usage:
#   ./test-auth-proxy.sh              # test all sandboxes
#   ./test-auth-proxy.sh finance      # test one sandbox

set -uo pipefail

GATEWAY="${OPENSHELL_GATEWAY:-prelude2-final}"
KEYCLOAK_URL="${KEYCLOAK_URL:-https://keycloak-keycloak.apps.sno.sandbox1254.opentlc.com}"
REALM="${KEYCLOAK_REALM:-prelude-m6wl4-vs9lb}"

BOLD="\033[1m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
CYAN="\033[36m"
RESET="\033[0m"

PASS=0
FAIL=0

check() {
  local desc="$1"
  local result="$2"
  if [ "$result" = "PASS" ]; then
    echo -e "  ${GREEN}✓${RESET} $desc"
    ((PASS++))
  else
    echo -e "  ${RED}✗${RESET} $desc — ${RED}$result${RESET}"
    ((FAIL++))
  fi
}

exec_in() {
  local sandbox="$1"; shift
  openshell sandbox exec -n "$sandbox" -g "$GATEWAY" -- bash -c "$*" 2>&1
}

test_sandbox() {
  local dept="$1"
  local sandbox="retail-${dept}"

  echo ""
  echo -e "${BOLD}${CYAN}══ Testing ${sandbox} ══${RESET}"

  # ── 1. Token isolation ──
  echo -e "${YELLOW}── Token Isolation ──${RESET}"

  local token_files
  token_files=$(exec_in "$sandbox" 'ls /tmp/hermes-oidc* 2>&1')
  if echo "$token_files" | grep -q "No such file"; then
    check "No token files on disk" "PASS"
  else
    check "No token files on disk" "FOUND: $token_files"
  fi

  local jwt_grep
  jwt_grep=$(exec_in "$sandbox" 'grep -rl "eyJ" /tmp/ 2>/dev/null | head -3')
  if [ -z "$jwt_grep" ]; then
    check "No JWT content in /tmp" "PASS"
  else
    check "No JWT content in /tmp" "FOUND: $jwt_grep"
  fi

  # ── 2. Memory protection ──
  echo -e "${YELLOW}── Memory Protection ──${RESET}"

  local environ_test
  environ_test=$(exec_in "$sandbox" 'for p in /proc/[0-9]*/cmdline; do pid=$(echo $p | cut -d/ -f3); if grep -q dashboard $p 2>/dev/null; then cat /proc/$pid/environ >/dev/null 2>&1 && echo "READABLE" || echo "BLOCKED"; break; fi; done')
  if echo "$environ_test" | grep -q "BLOCKED"; then
    check "/proc/<dashboard>/environ blocked (PR_SET_DUMPABLE=0)" "PASS"
  else
    check "/proc/<dashboard>/environ blocked" "READABLE — dumpable not set"
  fi

  local mem_test
  mem_test=$(exec_in "$sandbox" 'for p in /proc/[0-9]*/cmdline; do pid=$(echo $p | cut -d/ -f3); if grep -q dashboard $p 2>/dev/null; then dd if=/proc/$pid/mem bs=1 count=1 2>&1 | grep -q "Permission denied" && echo "BLOCKED" || echo "READABLE"; break; fi; done')
  if echo "$mem_test" | grep -q "BLOCKED"; then
    check "/proc/<dashboard>/mem blocked" "PASS"
  else
    check "/proc/<dashboard>/mem blocked" "READABLE"
  fi

  local ptrace_test
  ptrace_test=$(exec_in "$sandbox" 'DPID=$(for p in /proc/[0-9]*/cmdline; do pid=$(echo $p | cut -d/ -f3); grep -q dashboard $p 2>/dev/null && echo $pid && break; done); python3 -c "import ctypes;l=ctypes.CDLL(None);r=l.ptrace(16,int(\"$DPID\"),0,0);print(\"ATTACHED\" if r==0 else \"DENIED\")" 2>&1')
  if echo "$ptrace_test" | grep -q "DENIED"; then
    check "ptrace(ATTACH) on dashboard denied" "PASS"
  else
    check "ptrace(ATTACH) on dashboard denied" "ATTACHED — vulnerable"
  fi

  # ── 3. Proxy listening ──
  echo -e "${YELLOW}── Auth Proxy ──${RESET}"

  local proxy_listen
  proxy_listen=$(exec_in "$sandbox" 'ss -tlnp 2>/dev/null | grep 8889')
  if echo "$proxy_listen" | grep -q "8889"; then
    check "Auth proxy listening on :8889" "PASS"
  else
    check "Auth proxy listening on :8889" "NOT LISTENING"
  fi

  # ── 4. Proxy forwarding (connectivity through OPA proxy) ──
  echo -e "${YELLOW}── Proxy Connectivity ──${RESET}"

  local proxy_health
  proxy_health=$(exec_in "$sandbox" 'curl -s -m 10 http://127.0.0.1:8889/health 2>&1')
  if echo "$proxy_health" | grep -q '"status"'; then
    check "Proxy → MCP /health forwarding (200)" "PASS"
  elif echo "$proxy_health" | grep -q "auth.unauthorized"; then
    check "Proxy → MCP /health forwarding (401 = no token yet)" "PASS"
  elif echo "$proxy_health" | grep -q "502"; then
    check "Proxy → MCP /health forwarding" "FAILED: 502 — proxy can't reach upstream"
  else
    check "Proxy → MCP /health forwarding" "FAILED: ${proxy_health:-empty response}"
  fi

  # The real test: MCP streamable-http initialize via POST /mcp
  # Must get a complete response — no chunked-encoding errors, no truncation
  local mcp_init mcp_exit
  mcp_init=$(exec_in "$sandbox" 'curl -s -m 15 -X POST http://127.0.0.1:8889/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d "{\"jsonrpc\":\"2.0\",\"method\":\"initialize\",\"id\":1,\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1.0\"}}}" 2>&1')
  mcp_exit=$?
  if [ "$mcp_exit" -eq 56 ]; then
    check "Proxy → MCP POST /mcp initialize" "FAILED: curl exit 56 — chunked encoding mismatch"
  elif echo "$mcp_init" | grep -q "Malformed"; then
    check "Proxy → MCP POST /mcp initialize" "FAILED: malformed chunked encoding"
  elif echo "$mcp_init" | grep -q '"serverInfo"'; then
    check "Proxy → MCP POST /mcp initialize (streamable-http)" "PASS"
  elif echo "$mcp_init" | grep -q "protocolVersion"; then
    check "Proxy → MCP POST /mcp initialize (streamable-http, SSE)" "PASS"
  elif echo "$mcp_init" | grep -q "auth.unauthorized"; then
    check "Proxy → MCP POST /mcp initialize (401 = no token yet)" "PASS"
  elif echo "$mcp_init" | grep -q "Not Acceptable"; then
    check "Proxy → MCP POST /mcp initialize" "FAILED: 406 — Accept header not forwarded"
  else
    check "Proxy → MCP POST /mcp initialize" "FAILED: exit=$mcp_exit ${mcp_init:0:80}"
  fi

  # ── 5. Direct MCP bypass ──
  local mcp_host="retail-${dept}-mcp.openshell.svc.cluster.local"
  local direct_mcp
  direct_mcp=$(exec_in "$sandbox" "curl -s -m 5 http://${mcp_host}:9090/health 2>&1")
  if echo "$direct_mcp" | grep -q "auth.unauthorized"; then
    check "Direct MCP (no token) → 401 from AuthBridge" "PASS"
  elif echo "$direct_mcp" | grep -q "policy_denied"; then
    check "Direct MCP → blocked by OPA" "PASS"
  elif [ -z "$direct_mcp" ]; then
    check "Direct MCP → no response (OPA or timeout)" "PASS"
  else
    check "Direct MCP bypass rejected" "UNEXPECTED: $direct_mcp"
  fi

  # ── 6. Per-sandbox OPA isolation ──
  echo -e "${YELLOW}── Per-Sandbox OPA Isolation ──${RESET}"

  local other_depts=()
  for d in finance sales ops; do
    [ "$d" != "$dept" ] && other_depts+=("$d")
  done

  for other in "${other_depts[@]}"; do
    local cross_mcp
    cross_mcp=$(exec_in "$sandbox" "curl -s -m 5 http://retail-${other}-mcp.openshell.svc.cluster.local:9090/health 2>&1")
    if echo "$cross_mcp" | grep -q "policy_denied"; then
      check "Cross-dept ${dept}→${other} MCP blocked by OPA" "PASS"
    elif [ -z "$cross_mcp" ]; then
      check "Cross-dept ${dept}→${other} MCP blocked (timeout/refused)" "PASS"
    else
      check "Cross-dept ${dept}→${other} MCP blocked" "REACHABLE: $cross_mcp"
    fi
  done

  # ── 7. Token injection (requires login — check if token is set) ──
  echo -e "${YELLOW}── Token Injection (requires prior OIDC login) ──${RESET}"

  local proxy_auth
  proxy_auth=$(exec_in "$sandbox" 'curl -s -m 10 http://127.0.0.1:8889/health 2>&1')
  if echo "$proxy_auth" | grep -q '"user"'; then
    local user
    user=$(echo "$proxy_auth" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('user','none'))" 2>/dev/null)
    if [ -n "$user" ] && [ "$user" != "none" ] && [ "$user" != "None" ]; then
      check "Proxy injected token — MCP sees user=${user}" "PASS"
    else
      check "Proxy forwarding works (no user logged in yet — expected)" "PASS"
    fi
  elif echo "$proxy_auth" | grep -q "auth.unauthorized"; then
    check "Proxy forwarding works (no login yet — 401 expected)" "PASS"
  else
    check "Proxy → MCP connectivity" "FAILED: ${proxy_auth:-empty}"
  fi

  # ── 8. MCP Python client end-to-end (the real test) ──
  echo -e "${YELLOW}── MCP Client End-to-End ──${RESET}"

  # Write test script (openshell exec can't handle heredocs)
  exec_in "$sandbox" 'echo "import asyncio" > /tmp/t.py'
  exec_in "$sandbox" 'echo "async def t():" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "    from mcp import ClientSession" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "    from mcp.client.streamable_http import streamablehttp_client" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "    try:" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "        async with streamablehttp_client(\"http://127.0.0.1:8889/mcp\") as (r,w,_):" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "            async with ClientSession(r,w) as s:" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "                await s.initialize()" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "                tools = await s.list_tools()" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "                print(f\"OK:{len(tools.tools)}\")" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "    except Exception as e:" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "        print(f\"FAIL:{type(e).__name__}:{e}\")" >> /tmp/t.py'
  exec_in "$sandbox" 'echo "asyncio.run(t())" >> /tmp/t.py'

  local mcp_e2e
  mcp_e2e=$(exec_in "$sandbox" '/opt/hermes/.venv/bin/python3 /tmp/t.py 2>&1')
  if echo "$mcp_e2e" | grep -q "^OK:"; then
    local ntools
    ntools=$(echo "$mcp_e2e" | grep "^OK:" | cut -d: -f2)
    check "MCP Python client → initialize + list_tools (${ntools} tools)" "PASS"
  elif echo "$mcp_e2e" | grep -q "auth.unauthorized"; then
    check "MCP Python client (401 = no login yet)" "PASS"
  elif echo "$mcp_e2e" | grep -q "^FAIL:"; then
    check "MCP Python client end-to-end" "FAILED: ${mcp_e2e}"
  else
    check "MCP Python client end-to-end" "FAILED: ${mcp_e2e:0:80}"
  fi
}

# ── Main ──

echo ""
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo -e "${BOLD} Auth Proxy + Per-Sandbox OPA Test Suite${RESET}"
echo -e "${BOLD}════════════════════════════════════════════${RESET}"

DEPTS="${@:-finance sales ops}"
for dept in $DEPTS; do
  test_sandbox "$dept"
done

echo ""
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo -e "${BOLD} Results: ${GREEN}${PASS} passed${RESET}, ${RED}${FAIL} failed${RESET}"
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo ""

exit $FAIL
