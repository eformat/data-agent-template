#!/bin/bash
# Hermes Agent sandbox entrypoint for the retail demo.
#
# Port layout:
#   Hermes Gateway (chat API):  127.0.0.1:18642
#   Hermes Dashboard (web UI):  0.0.0.0:9119 (gated mode — Hermes OAuth)
#
# Dashboard binds 0.0.0.0 which activates Hermes gated/OAuth mode.
# Users authenticate via Keycloak (OpenShift identity) — no external OAuth proxy needed.
# The OpenShell relay connects to 127.0.0.1:9119 inside the sandbox.
#
# Secrets: OPENAI_API_KEY is passed via `env` on the sandbox create command.

export TERM=xterm-256color
export HERMES_HOME=/sandbox/.hermes
export HERMES_TUI_DIR="/opt/hermes/ui-tui"

# Source .env for additional settings
set -a
[ -f /sandbox/.hermes/.env ] && source /sandbox/.hermes/.env
[ -f /sandbox/.hermes/profiles/retail-sales/.env ] && source /sandbox/.hermes/profiles/retail-sales/.env
set +a

# Self-hosted OIDC provider for Hermes gated mode (Keycloak)
export HERMES_DASHBOARD_OIDC_ISSUER="${HERMES_DASHBOARD_OIDC_ISSUER:-https://keycloak-keycloak.apps.sno.sandbox1254.opentlc.com/realms/prelude-m6wl4-vs9lb}"
export HERMES_DASHBOARD_OIDC_CLIENT_ID="${HERMES_DASHBOARD_OIDC_CLIENT_ID:-hermes-dashboard}"

# Public URL (for OAuth redirects)
PUBLIC_URL="${HERMES_PUBLIC_URL:-https://retail-hermes.apps.prelude-m6wl4-vs9lb.sandbox1832.opentlc.com}"

# Write config.yaml files with the real API key and OAuth config.
for profile_dir in /sandbox/.hermes/profiles/retail-*/; do
  [ -d "$profile_dir" ] || continue
  dept=$(basename "$profile_dir" | sed 's/retail-//')
  cat > "${profile_dir}/config.yaml" << CFGEOF
model:
  provider: custom
  model: kimi-k2-6
  base_url: http://maas.apps.ocp.cloud.rhai-tmm.dev/prelude-maas/kimi-k2-6/v1
  api_key: "${OPENAI_API_KEY}"
dashboard:
  theme: redhat
  public_url: "${PUBLIC_URL}"
mcp_servers:
  retail-${dept}:
    url: http://retail-${dept}-mcp.openshell.svc.cluster.local:9090/mcp
CFGEOF
done

cat > /sandbox/.hermes/config.yaml << CFGEOF
model:
  provider: custom
  model: kimi-k2-6
  base_url: http://maas.apps.ocp.cloud.rhai-tmm.dev/prelude-maas/kimi-k2-6/v1
  api_key: "${OPENAI_API_KEY}"
dashboard:
  theme: redhat
  public_url: "${PUBLIC_URL}"
mcp_servers: {}
CFGEOF

# Skip config migrate — it overwrites the heredoc configs with cached values

# Start gateway on internal-only port
API_SERVER_ENABLED=true API_SERVER_PORT=18642 API_SERVER_HOST=127.0.0.1 \
  /usr/local/bin/hermes gateway run --accept-hooks &
GATEWAY_PID=$!

# Wait for gateway to be healthy AND MCP tools discovered before starting dashboard.
# Without this, the first chat session sees 0 MCP tools.
for i in $(seq 1 30); do
  if curl -sf --max-time 2 "http://127.0.0.1:18642/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
sleep 3

# Dashboard on 0.0.0.0:9119 — non-loopback activates Hermes gated/OAuth mode.
# Users authenticate via Keycloak OIDC. The TUI wildcard-bind patch in the
# Containerfile ensures the TUI connects to 127.0.0.1 (not 0.0.0.0).
GATEWAY_HEALTH_URL="http://127.0.0.1:18642" \
  /usr/local/bin/hermes dashboard \
    --host 0.0.0.0 \
    --port 9119 \
    --skip-build \
    --no-open &
DASHBOARD_PID=$!

sleep infinity
