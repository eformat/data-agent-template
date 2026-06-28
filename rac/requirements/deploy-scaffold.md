---
schema_version: 1
id: RAC-KW855PSFC7QN
type: requirement
---
# Deploy and Scaffold — Project Generation and OpenShift Manifests

## Problem

Creating a new domain agent requires dozens of boilerplate files: Containerfiles, kustomize manifests, deployment configs, scripts, test stubs, and CI configuration. Without a scaffold generator, each new domain project copy-pastes from an existing one, leading to drift and inconsistency. Deploy manifests must be correct-by-construction from the DomainConfig.

## Requirements

- [REQ-001] `data-agent init <name>` MUST scaffold a complete project directory including: agent-config.yaml, system_prompt.md, agent app.py, MCP server.py, eval pipeline.py, test stubs (conftest.py, test_tools.py), pyproject.toml, README.md, Makefile, and load-data.sh script.
- [REQ-002] `render_deploy_tree(config, output_dir)` MUST generate OpenShift/K8s manifests from DomainConfig including: agent deployment + service + route + PVC + buildconfig + imagestream, MCP server deployment + service + buildconfig + imagestream, kustomization.yaml for both, and common resources (DSPA, MLflow RBAC, S3 secret, MaaS key secret, Chainlit secret).
- [REQ-003] Template variables MUST be flattened from DomainConfig: DOMAIN_NAME, DOMAIN_DISPLAY_NAME, NAMESPACE, REPLICAS, resource limits (CPU/memory for agent and MCP), MODEL_NAME, MODEL_ENDPOINT, TRINO_HOST, TRINO_PORT, TRINO_CATALOG, TRINO_SCHEMA, MLFLOW_TRACKING_URI, MLFLOW_WORKSPACE, S3_ENDPOINT, S3_BUCKET, CHAINLIT_PVC_SIZE, ROUTE_TIMEOUT, ROUTE_TLS_TERMINATION.
- [REQ-004] CHAINLIT_AUTH_SECRET MUST be generated as a random 32-byte hex string, unique per scaffold run.
- [REQ-005] All generated scripts MUST be made executable (chmod +x).
- [REQ-006] Containerfiles MUST use UBI base images for OpenShift compatibility.
- [REQ-007] The namespace MUST default to config.domain_name if not explicitly set in DeploymentConfig.
- [REQ-008] S3 endpoint host MUST be parsed from the full endpoint URL for manifest templating.

## Success Metrics

- `data-agent init <name>` produces a project that passes `data-agent validate` and `data-agent dev` without manual edits.
- Generated manifests apply cleanly to an OpenShift cluster via `oc apply -k`.
- No hardcoded domain-specific values leak into the scaffold — everything is driven by DomainConfig.

## Risks

- OpenShift API version changes may invalidate generated manifests.
- Template variable substitution uses safe_substitute, so unrecognized variables silently pass through rather than failing.

## Assumptions

- Target deployment platform is OpenShift 4.x with BuildConfig support (source-to-image builds).
- S3 storage (MinIO or ODF) is available for MLflow artifact storage.
- Kustomize is the deployment strategy (not Helm).

## Related Decisions

RAC-KW86NH6F62TY
