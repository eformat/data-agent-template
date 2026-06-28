---
schema_version: 1
id: RAC-KW89BZAQ7A1Y
type: decision
---
# GitOps Data Platform with ArgoCD App-of-Apps, age/SOPS Secrets, and Sync-Wave Orchestration

## Context

Data agents depend on four platform components — Trino (SQL), Nessie (Iceberg catalog), MinIO (S3 storage), SpiceDB (authorization) — that must be deployed together on OpenShift with correct wiring, dependency ordering, and secret management. The scaffold generator (`data-agent init`) produces agent and MCP server manifests but not the underlying infrastructure. Three proven reference implementations exist:

- **Application manifests:** `https://github.com/eformat/data-agent-ctf/tree/main/applications`
- **Secrets management:** `https://github.com/eformat/argocd-avp-sops-teams`
- **App-of-apps orchestration:** `https://github.com/eformat/data-agent-ctf/tree/main/app-of-apps`

## Decision

We adopt a GitOps deployment strategy using ArgoCD's app-of-apps pattern with age/SOPS secret encryption and sync-wave orchestration, codified into the scaffold generator. Specifically:

1. **App-of-apps Helm chart** — a root ArgoCD Application deploys all platform components as child Application CRs. Cluster-scoped values (`appsDomain`, `namespace`, `gitRepo`, `gitRevision`, `inference`) drive all child templates. Helm helpers compute derived URLs (Keycloak, inference).

2. **Sync-wave ordering** — wave 0 (SOPS-encrypted secrets) → wave 1 (MinIO, SpiceDB operator) → wave 2 (Trino + Nessie, SpiceDB instance, schema-load jobs) → wave 3+ (agents, MCP servers). PostSync hook Jobs handle schema loading, table population, and fixture seeding.

3. **age/SOPS secrets** — all secrets encrypted at rest in Git via SOPS with age key wrapping. A `.sops.yaml` at the repo root maps path patterns to age public keys. ArgoCD decrypts at sync time via a `sops-age-kustomize` ConfigManagementPlugin sidecar with the age private key mounted from a Kubernetes Secret. A `secrets-example.yaml` template documents all required keys.

4. **Platform components** — Trino via upstream Helm chart (coordinator-only, Iceberg/Nessie catalogs, S3 credentials from Secret), Nessie as standalone Deployment, MinIO as single-pod with PVC, SpiceDB via OLM operator + CRD instance with PostgreSQL backend.

5. **Multi-source Applications** — child ArgoCD Applications combine external Helm charts with git-based values files from the same repo, keeping upstream charts unforked.

## Consequences

**Easier:** A new environment deploys the full platform via a single ArgoCD Application CR with three value changes (`appsDomain`, `namespace`, `gitRevision`). Secrets never appear in Git plaintext. Sync-wave ordering eliminates manual dependency management. The scaffold generator produces the complete platform, not just agents.

**Harder:** age private key distribution to the ArgoCD repo server is a manual bootstrap step with no automated path. ArgoCD sync-waves guarantee resource creation order but not pod readiness — init jobs must poll for service availability. SpiceDB Operator and CloudNativePG must be available via OLM. Trino upstream Helm chart version pinning requires maintenance when breaking changes occur.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

- **Helm-only (no ArgoCD)** — rejected because it provides no GitOps reconciliation, drift detection, or automated sync. Manual `helm install` ordering is error-prone and not self-healing.
- **Terraform/Crossplane for infrastructure** — rejected because the target is application-layer deployment on an existing OpenShift cluster, not infrastructure provisioning. ArgoCD is the standard GitOps tool in the OpenShift ecosystem.
- **Sealed Secrets instead of age/SOPS** — rejected because Sealed Secrets are cluster-scoped (re-encryption required per cluster) and don't support team-scoped key hierarchies. age/SOPS with path-regex rules enables per-team encryption with keys that are portable across clusters.
- **Vault (HashiCorp) for secrets** — rejected as over-engineered for the current scale. Vault requires its own HA deployment, unsealing, and policy management. age/SOPS is zero-infrastructure — the encryption key is a single file.
- **Single monolithic Helm chart** — rejected because it prevents using upstream charts (Trino, SpiceDB operator) unmodified. Multi-source ArgoCD Applications let us consume upstream charts with local values overrides.

## Related Requirements

RAC-KW88Z3P6KF70
