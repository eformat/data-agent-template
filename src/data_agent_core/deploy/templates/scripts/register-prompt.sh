#!/bin/bash
set -euo pipefail

NAMESPACE="${NAMESPACE}"
PROMPT_NAME="${MLFLOW_PROMPT_NAME}"
PROMPT_FILE="system_prompt.md"
COMMIT_MSG="$${1:-update}"

echo "--- Port-forwarding MLflow ---"
oc -n redhat-ods-applications port-forward svc/mlflow 5000:8443 &
PF_PID=$$!
sleep 3

cleanup() { kill $${PF_PID} 2>/dev/null || true; }
trap cleanup EXIT

echo "--- Registering prompt: $${PROMPT_NAME} ---"
python3 -c "
import mlflow
mlflow.set_tracking_uri('https://localhost:5000')
template = open('$${PROMPT_FILE}').read()
mlflow.genai.register_prompt(
    name='$${PROMPT_NAME}',
    template=template,
    commit_message='$${COMMIT_MSG}',
)
versions = mlflow.MlflowClient().search_model_versions(f\"name='{PROMPT_NAME}'\")
latest = max(v.version for v in versions)
mlflow.genai.set_prompt_alias('$${PROMPT_NAME}', 'production', int(latest))
print(f'Registered {PROMPT_NAME} v{latest}, alias=production')
"
