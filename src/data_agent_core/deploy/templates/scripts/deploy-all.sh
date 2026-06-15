#!/bin/bash
set -euo pipefail

NAMESPACE="${NAMESPACE}"
DOMAIN="${DOMAIN_NAME}"

echo "=== Deploying $${DOMAIN} agent to $${NAMESPACE} ==="

# Create namespace
oc new-project "$${NAMESPACE}" 2>/dev/null || oc project "$${NAMESPACE}"

# Apply common resources (secrets, RBAC, DSPA)
echo "--- Applying common resources ---"
oc apply -k deploy/

# Build and deploy MCP server
echo "--- Building MCP server ---"
oc apply -k agents/$${DOMAIN}-mcp-server/deploy/
oc start-build $${DOMAIN}-mcp-server --from-dir=agents/$${DOMAIN}-mcp-server/ --follow

# Build and deploy agent
echo "--- Building agent ---"
oc apply -k agents/$${DOMAIN}-agent/deploy/
oc start-build $${DOMAIN}-agent --from-dir=agents/$${DOMAIN}-agent/ --follow

echo "=== Deployment complete ==="
oc get route $${DOMAIN}-agent -o jsonpath='Agent URL: https://{.spec.host}{"\n"}'
