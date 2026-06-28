---
schema_version: 1
id: RAC-KW855NQNP9DY
type: requirement
---
# MLflow Integration — Portable Tracing and Prompt Registry

## Problem

Agents deployed on Red Hat OpenShift AI (RHOAI) must integrate with MLflow for tracing, experiment tracking, and prompt management — but RHOAI 3.4 and 3.5 have incompatible MLflow configurations (different tracking URI patterns, workspace support, token auth). The integration must work across both versions without code changes, and gracefully degrade when MLflow is unavailable (e.g., dev mode).

## Requirements

- [REQ-001] `init_mlflow()` MUST configure MLflow from environment variables: MLFLOW_TRACKING_URI, MLFLOW_TRACKING_TOKEN_FILE, MLFLOW_WORKSPACE.
- [REQ-002] RHOAI 3.5 compatibility: tracking URI format `https://mlflow...svc:8443/mlflow`, workspace support via `mlflow.set_workspace()` + `store._workspace_support = True`.
- [REQ-003] RHOAI 3.4 compatibility: tracking URI format `https://mlflow...svc:8443` (no /mlflow suffix), standard experiment API.
- [REQ-004] TLS certificate handling MUST merge the system CA bundle (/etc/pki/tls/certs/ca-bundle.crt) with the Kubernetes service CA (/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt) into a combined bundle, setting REQUESTS_CA_BUNDLE.
- [REQ-005] Token file auth MUST read MLFLOW_TRACKING_TOKEN_FILE if the file exists and set the appropriate env var for MLflow SDK authentication.
- [REQ-006] LangChain autolog MUST be enabled via `mlflow.langchain.autolog()` to automatically trace all LangChain class invocations.
- [REQ-007] Prompt registration MUST use `mlflow.genai.register_prompt()` and `mlflow.genai.set_prompt_alias()` when MLflow >= 3.10 is available, with the system prompt stored in the Prompt Registry.
- [REQ-008] PromptManager MUST provide a 60-second TTL cache for prompt lookups, falling back to the default prompt if MLflow is unavailable.
- [REQ-009] All MLflow initialization MUST gracefully continue with print warnings if MLflow is unreachable — never crash the agent on MLflow failure.

## Success Metrics

- Same agent binary deploys on RHOAI 3.4 and 3.5 without config changes beyond the tracking URI.
- Agent starts and serves queries even when MLflow is completely unavailable.
- All LangChain tool calls appear as spans in MLflow traces.

## Risks

- MLflow API changes across versions may break workspace support detection or prompt registry integration.
- CA bundle merging via tempfile may fail in read-only container filesystems.

## Assumptions

- MLflow is deployed as a managed service on RHOAI, not self-hosted.
- The Kubernetes service account has a valid service-ca.crt for TLS.

## Related Decisions

RAC-KW86NGKYXV2C
