---
schema_version: 1
id: RAC-KW88Z3P6KF70
type: requirement
---
# Data Platform Deployment — Trino, Nessie, MinIO, SpiceDB on OpenShift

## Problem

Data agents require a complete lakehouse platform — Trino for SQL, Nessie for Iceberg catalog versioning, MinIO for S3 object storage, and SpiceDB for authorization — deployed and wired together on OpenShift. Without a scaffolded, GitOps-driven deployment, each environment is hand-assembled, leading to configuration drift, missing secrets, incorrect service wiring, and inconsistent sync ordering. The scaffold generator (`data-agent init`) currently produces agent and MCP server manifests but not the underlying data platform infrastructure they depend on.

Three existing repositories provide the proven deployment patterns this requirement codifies:

- **Application manifests:** `https://github.com/eformat/data-agent-ctf/tree/main/applications` — Kustomize + Helm manifests for Trino, Nessie, MinIO, SpiceDB, Keycloak, and supporting components.
- **Secrets management:** `https://github.com/eformat/argocd-avp-sops-teams` — age/SOPS encryption with ArgoCD ConfigManagementPlugin sidecars for team-scoped secret decryption.
- **App-of-apps orchestration:** `https://github.com/eformat/data-agent-ctf/tree/main/app-of-apps` — ArgoCD Helm chart that deploys all platform components as child Application CRs with sync-wave ordering.

## Requirements

### Platform Applications

- [REQ-001] The scaffold MUST generate deployable manifests for four data platform components: Trino (SQL engine), Nessie (Iceberg catalog), MinIO (S3 storage), and SpiceDB (authorization). Reference implementation: `https://github.com/eformat/data-agent-ctf/tree/main/applications`.
- [REQ-002] Trino MUST be deployed via the upstream Helm chart (`https://trinodb.github.io/charts/trino`) with a git-based values file. The coordinator MUST run with `workers: 0` and `includeCoordinator: true` for single-node dev/demo deployments.
- [REQ-003] Trino catalogs MUST be configured as Iceberg connectors backed by Nessie, with one catalog per domain dataset group (e.g., finance, sales, ops). Each catalog MUST reference Nessie via `iceberg.nessie-catalog.uri=http://nessie:19120/api/v2` with a per-catalog Nessie branch and S3 warehouse directory.
- [REQ-004] Nessie MUST be deployed as a standalone Deployment (`ghcr.io/projectnessie/nessie`) exposing the REST/gRPC API on port 19120, providing version-controlled Iceberg catalog metadata.
- [REQ-005] MinIO MUST be deployed as a single-pod Deployment with a PersistentVolumeClaim, exposing the S3 API on port 9000 and the web console on port 9001. Credentials MUST be injected via a `minio-credentials` Secret (MINIO_ROOT_USER, MINIO_ROOT_PASSWORD).
- [REQ-006] SpiceDB MUST be deployed via the SpiceDB Operator (OLM subscription) with a SpiceDBCluster CRD instance backed by PostgreSQL. The operator MUST be installed first (sync-wave 1), with the instance created after (sync-wave 2).
- [REQ-007] A SpiceDB schema-load Job MUST run as a post-sync hook to populate the authorization schema and seed fixtures from a ConfigMap. The job MUST wait for the SpiceDB HTTP API (port 8443) to be ready before loading.
- [REQ-008] Trino credentials (S3_ACCESS_KEY, S3_SECRET_KEY) MUST be sourced from a `trino-credentials` Secret that maps to the MinIO root credentials, injected into the Trino pod via `envFrom`.

### Secrets Management (age/SOPS)

- [REQ-009] All secrets MUST be encrypted at rest in Git using SOPS with age key wrapping. A `.sops.yaml` file at the repo root MUST define `creation_rules` with `path_regex` patterns mapping encrypted files to age public keys.
- [REQ-010] ArgoCD MUST decrypt secrets at sync time via a ConfigManagementPlugin sidecar (`sops-age-kustomize`) running on the repo server, with the age private key mounted from a Kubernetes Secret. Reference implementation: `https://github.com/eformat/argocd-avp-sops-teams/blob/main/bootstrap/setup-cr.yaml`.
- [REQ-011] Secrets MUST be deployed at sync-wave 0 (before all other applications) so consumers can reference them via `secretRef` or `envFrom`.
- [REQ-012] The scaffold MUST generate a `secrets-example.yaml` template listing all required secret keys (minio-credentials, trino-credentials, spicedb-config, spicedb-token) with placeholder values, plus instructions for encrypting with `sops -e`.

### ArgoCD App-of-Apps Orchestration

- [REQ-013] The scaffold MUST generate an ArgoCD app-of-apps Helm chart that deploys all platform components as child Application CRs. Reference implementation: `https://github.com/eformat/data-agent-ctf/tree/main/app-of-apps`.
- [REQ-014] The app-of-apps chart MUST accept cluster-scoped values: `appsDomain` (OpenShift apps subdomain), `namespace` (target namespace), `gitRepo` (source repo URL), `gitRevision` (branch/tag), and `inference` (MaaS endpoint host + path).
- [REQ-015] Helm helpers MUST compute derived URLs from values: Keycloak host, Keycloak issuer URL, token endpoint URL, and inference URL — so child Application templates reference computed values, not hardcoded URLs.
- [REQ-016] Sync-wave ordering MUST enforce the dependency chain: wave 0 (secrets) → wave 1 (MinIO, SpiceDB operator) → wave 2 (Trino, Nessie, SpiceDB instance, schema-load jobs) → wave 3+ (agents, MCP servers, sandboxes).
- [REQ-017] The root ArgoCD Application MUST use automated sync with prune and selfHeal enabled, targeting the `openshift-gitops` namespace.
- [REQ-018] Child Applications MUST support multi-source deployment: external Helm charts (Trino, SpiceDB operator) combined with git-based values files from the same repo.

### Init Jobs and Post-Sync Hooks

- [REQ-019] Post-sync init Jobs (schema load, table population, fixture seeding) MUST use ArgoCD hook annotations: `argocd.argoproj.io/hook: PostSync` and `argocd.argoproj.io/hook-delete-policy: BeforeHookCreation`.
- [REQ-020] A Trino tables-job MUST run post-sync to populate sample Iceberg tables from SQL scripts stored in a ConfigMap, connecting to `trino:8080`.

## Success Metrics

- `data-agent init <name>` scaffolds a complete app-of-apps that deploys the full data platform via a single ArgoCD Application CR.
- Platform components start in dependency order and reach healthy state without manual intervention.
- Secrets are never committed to Git in plaintext — only SOPS-encrypted `.enc` files are stored.
- A new environment can be stood up by changing `appsDomain`, `namespace`, and `gitRevision` in the app-of-apps values.

## Risks

- Operator availability: SpiceDB Operator and CloudNativePG (for PostgreSQL) must be installable via OLM on the target cluster.
- SOPS/age key distribution: age private keys must be securely provisioned to the ArgoCD repo server before first sync — no automated bootstrap path exists.
- Trino Helm chart version pinning: upstream chart breaking changes could invalidate generated values files.
- Sync-wave timing: ArgoCD sync-waves do not guarantee pod readiness, only resource creation order — init jobs must poll for service availability.

## Assumptions

- Target platform is OpenShift 4.x with ArgoCD (OpenShift GitOps operator) installed.
- OLM (Operator Lifecycle Manager) is available for installing SpiceDB and CloudNativePG operators.
- A single namespace deployment is sufficient (all components in one namespace).
- MinIO single-pod deployment is acceptable for dev/demo; production would use the MinIO Operator or ODF.
- The `sops-age-kustomize` ArgoCD plugin is pre-configured on the cluster's ArgoCD instance.

## Related Decisions

RAC-KW86NH6F62TY
RAC-KW86NG1N17HB
RAC-KW86NG7TYK79
RAC-KW89BZAQ7A1Y
