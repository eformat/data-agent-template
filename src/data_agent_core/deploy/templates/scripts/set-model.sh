#!/bin/bash
set -euo pipefail

NAMESPACE="${NAMESPACE}"
DOMAIN="${DOMAIN_NAME}"

if [ -z "$${1:-}" ] || [ -z "$${2:-}" ]; then
    echo "Usage: $$0 <model-name> <model-endpoint>"
    echo "Example: $$0 kimi-k2-6 http://maas.example.com/v1"
    exit 1
fi

MODEL_NAME="$$1"
MODEL_ENDPOINT="$$2"

echo "Setting model to $${MODEL_NAME} at $${MODEL_ENDPOINT}"
oc -n "$${NAMESPACE}" set env deployment/$${DOMAIN}-agent \
    MODEL_NAME="$${MODEL_NAME}" \
    MODEL_ENDPOINT="$${MODEL_ENDPOINT}"

echo "Waiting for rollout..."
oc -n "$${NAMESPACE}" rollout status deployment/$${DOMAIN}-agent --timeout=120s
echo "Done."
