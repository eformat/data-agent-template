#!/bin/bash
# Deploy the Hermes sandbox on OpenShell with OAuth and WebSocket support.
#
# Creates:
#   - OAuth proxy deployment + service + route (reencrypt TLS)
#   - OpenShell sandbox running Hermes (hermes-start.sh entrypoint)
#   - Service endpoint exposure (port 9119)
#
# Secret injection:
#   OPENAI_API_KEY is passed via `env` on the sandbox create command.
#   hermes-start.sh writes config.yaml with the key via heredoc at startup.
#   No secrets in the container image.
#
# Prerequisites:
#   - OpenShell gateway running in openshell namespace
#   - openshell CLI connected to the gateway (openshell gateway add)
#   - oc port-forward to the gateway on port 10880
#   - MCP servers deployed (retail-finance/sales/ops-mcp)
#   - SpiceDB + Trino deployed
#
# Usage:
#   export OPENAI_API_KEY="sk-..."
#   export OPENSHELL_GATEWAY="prelude2-final"
#   ./deploy-sandbox.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
NS="openshell"
GATEWAY="${OPENSHELL_GATEWAY:-prelude2-final}"
HERMES_IMAGE="${HERMES_IMAGE:-quay.io/eformat/hermes-openshell:latest}"
APPS_DOMAIN="${APPS_DOMAIN:-$(oc get ingresses.config cluster -o jsonpath='{.spec.domain}')}"

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPENAI_API_KEY must be set"
  exit 1
fi

echo "=== Deploying Hermes Sandbox ==="

# 1. Build .env files with secrets (injected at deploy time, not in git).
echo "--- Preparing secrets ---"
UPLOAD_DIR=$(mktemp -d)
mkdir -p "$UPLOAD_DIR/profiles/retail-"{finance,sales,ops}

ENV_CONTENT="OPENAI_API_KEY=${OPENAI_API_KEY}
GATEWAY_ALLOW_ALL_USERS=true
TERM=xterm-256color"

echo "$ENV_CONTENT" > "$UPLOAD_DIR/.env"
for dept in finance sales ops; do
  echo "$ENV_CONTENT" > "$UPLOAD_DIR/profiles/retail-${dept}/.env"
done

# 2. Create Route (reencrypt TLS, direct to OpenShell gateway — Hermes handles OAuth via Keycloak)
echo "--- Creating Route ---"
DEST_CA=$(oc get secret openshell-server-tls -n "$NS" -o jsonpath='{.data.ca\.crt}' | base64 -d)

cat << ROUTEEOF | oc apply -n "$NS" -f -
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: retail-hermes
  namespace: $NS
  annotations:
    haproxy.router.openshift.io/timeout: "3600s"
spec:
  host: retail-hermes.${APPS_DOMAIN}
  tls:
    termination: reencrypt
    insecureEdgeTerminationPolicy: Redirect
    destinationCACertificate: |
$(echo "$DEST_CA" | sed 's/^/      /')
  port:
    targetPort: grpc
  to:
    kind: Service
    name: openshell
ROUTEEOF

# 3. Create sandbox
echo "--- Creating sandbox ---"
openshell sandbox delete retail-hermes -g "$GATEWAY" 2>/dev/null || true
sleep 5

# sandbox create hangs (SSH session stays open), so background it and
# poll status separately. Trap ensures cleanup on any exit.
openshell sandbox create -g "$GATEWAY" \
  --name retail-hermes \
  --from "$HERMES_IMAGE" \
  --upload "$UPLOAD_DIR:/sandbox/.hermes" \
  --policy "$DEPLOY_DIR/policy-retail.yaml" \
  --no-tty \
  -- env OPENAI_API_KEY="${OPENAI_API_KEY}" \
         GATEWAY_ALLOW_ALL_USERS=true \
         HERMES_DASHBOARD_OIDC_ISSUER="${HERMES_DASHBOARD_OIDC_ISSUER:-https://keycloak-keycloak.apps.sno.sandbox1254.opentlc.com/realms/prelude-m6wl4-vs9lb}" \
         HERMES_DASHBOARD_OIDC_CLIENT_ID="${HERMES_DASHBOARD_OIDC_CLIENT_ID:-hermes-dashboard}" \
         /usr/local/bin/hermes-start.sh </dev/null >/dev/null 2>&1 &
CREATE_PID=$!
trap 'kill $CREATE_PID 2>/dev/null; rm -rf "$UPLOAD_DIR"' EXIT

echo "Waiting for sandbox to be Ready..."
for i in $(seq 1 60); do
  STATUS=$(openshell sandbox list -g "$GATEWAY" 2>/dev/null | grep retail-hermes | awk '{print $NF}' || echo "")
  if [ "$STATUS" = "Ready" ]; then
    echo "Sandbox ready after ~${i}0s"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "ERROR: Sandbox did not reach Ready state"
    exit 1
  fi
  sleep 10
done

# 4. Expose service — retry because sandbox may still be registering endpoints
echo "--- Exposing service ---"
for i in $(seq 1 10); do
  if openshell service expose retail-hermes 9119 -g "$GATEWAY" 2>&1; then
    break
  fi
  if [ "$i" -eq 10 ]; then
    echo "ERROR: Failed to expose service after 10 attempts"
    exit 1
  fi
  echo "  Attempt $i failed, retrying in 3s..."
  sleep 3
done

# 5. Clean up (trap handles CREATE_PID and UPLOAD_DIR)
trap - EXIT
kill $CREATE_PID 2>/dev/null || true
rm -rf "$UPLOAD_DIR"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Dashboard: https://retail-hermes.${APPS_DOMAIN}"
echo "Profile: retail-sales (active)"
echo ""
