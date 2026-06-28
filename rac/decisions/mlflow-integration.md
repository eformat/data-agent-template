---
schema_version: 1
id: RAC-KW86NGKYXV2C
type: decision
---
# Portable MLflow Init Across RHOAI 3.4 and 3.5 with Graceful Degradation

## Context

Agents deploy on Red Hat OpenShift AI (RHOAI) which bundles MLflow for tracing and experiment tracking. RHOAI 3.4 and 3.5 have incompatible MLflow configurations: different tracking URI patterns, workspace support, and token auth mechanisms. Agents must also run in dev mode where MLflow is entirely absent.

## Decision

We implement a single `init_mlflow()` function that handles both RHOAI versions via environment variables (MLFLOW_TRACKING_URI, MLFLOW_TRACKING_TOKEN_FILE, MLFLOW_WORKSPACE). It merges system and Kubernetes CA bundles for TLS, enables LangChain autolog, and registers prompts in MLflow Prompt Registry when available (>= 3.10). All MLflow failures produce warnings, never crashes — the agent continues serving without tracing.

## Consequences

**Easier:** Same agent binary deploys on RHOAI 3.4 and 3.5 with only a URI change. Agent starts and works even when MLflow is completely down. LangChain autolog traces all tool calls automatically.

**Harder:** CA bundle merging via tempfile may fail in read-only container filesystems. Workspace support detection relies on internal MLflow API (`store._workspace_support`), which could break in future versions. Graceful degradation means MLflow outages are silent — operators must monitor separately.

## Status

Accepted

## Category

Technical

## Alternatives Considered

- **Separate init paths per RHOAI version** — rejected because it requires version detection logic and doubles the maintenance surface.
- **MLflow as a hard dependency** — rejected because dev mode must work without MLflow, and agent availability must not depend on MLflow uptime.
- **OpenTelemetry instead of MLflow** — rejected because RHOAI bundles MLflow as the managed tracing solution, and MLflow's Prompt Registry provides prompt versioning that OTel does not.

## Related Requirements

RAC-KW855NQNP9DY
