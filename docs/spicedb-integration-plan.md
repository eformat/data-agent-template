# Plan: SpiceDB Platform Auth + Data Lakehouse + Agent Access Control

## Context

OpenShell currently has two authorization layers:
- **Sandbox policy** (OPA/regorus) — controls what code can do inside a sandbox (network, filesystem, process). Staying as-is.
- **Platform RBAC** (hand-rolled 2-role check in `authz.rs`) — controls who can call gRPC methods. Being replaced with SpiceDB.

This plan adds SpiceDB as the platform authorization database, deploys a data lakehouse (Trino) on OpenShift, builds an OpenShift console plugin for managing access control via an integrated AuthZed Playground, and deploys an agent through OpenShell with policy-governed access to the lakehouse.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenShift Cluster                         │
│                                                             │
│  ┌──────────────────────┐    ┌────────────────────────────┐ │
│  │  OpenShift Console   │    │  SpiceDB                   │ │
│  │  ┌────────────────┐  │    │  (authz database)          │ │
│  │  │ Console Plugin  │──────│  - gRPC :50051             │ │
│  │  │ (AuthZed       │  │    │  - HTTP :8443              │ │
│  │  │  Playground +  │  │    │  - PostgreSQL backend      │ │
│  │  │  Policy Mgmt)  │  │    └────────────────────────────┘ │
│  │  └────────────────┘  │                                   │
│  └──────────────────────┘    ┌────────────────────────────┐ │
│                              │  OpenShell Gateway          │ │
│  ┌──────────────────────┐    │  - authz.rs → SpiceDB      │ │
│  │  Trino Lakehouse     │    │  - sandbox policy → OPA    │ │
│  │  ┌────────┐          │    └────────────┬───────────────┘ │
│  │  │Coord.  │          │                 │                 │
│  │  │        ├──Workers │    ┌────────────▼───────────────┐ │
│  │  └───┬────┘          │    │  Agent Sandbox             │ │
│  │      │               │    │  (claude/hermes/openclaw)  │ │
│  │  ┌───▼────┐          │    │  - OPA sandbox policy      │ │
│  │  │Iceberg │ ← Nessie │    │  - L4/L7: Trino access    │ │
│  │  │on MinIO│          │    │    governed by SpiceDB     │ │
│  │  └────────┘          │    └────────────────────────────┘ │
│  └──────────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Component 1: SpiceDB Deployment

Deploy SpiceDB as a cluster service to serve as the platform authorization database.

**Schema** (initial design):
```zed
definition user {}

definition organization {
    relation admin: user
    relation member: user
    permission manage = admin
    permission use = admin + member
}

definition provider {
    relation organization: organization
    relation manager: user
    permission manage = manager + organization->manage
    permission use = organization->use
}

definition catalog {
    relation organization: organization
    relation owner: user
    relation reader: user | organization#member
    relation writer: user | organization#admin
    permission read = reader + writer + owner + organization->use
    permission write = writer + owner + organization->manage
    permission manage = owner + organization->manage
}

definition sandbox {
    relation owner: user
    relation organization: organization
    relation shared_with: user
    relation allowed_catalogs: catalog
    permission connect = owner + shared_with + organization->use
    permission delete = owner + organization->manage
    permission view = connect
}
```

**Deployment** (using existing manifests from `~/git/mcp-for-public-health/deploy/spicedb/`):
```bash
# 1. Install SpiceDB operator
oc apply --server-side -f https://github.com/authzed/spicedb-operator/releases/latest/download/bundle.yaml

# 2. Fix operator SCC + memory limits for OpenShift
oc apply --server-side -f deploy/spicedb/operator-install.yaml
oc patch deployment spicedb-operator -n spicedb-operator --type=json \
  --patch-file deploy/spicedb/operator-memory-patch.yaml

# 3. Deploy PostgreSQL + SpiceDBCluster
oc create ns spicedb
oc apply -k deploy/spicedb/ -n spicedb
```

**Integration with OpenShell Gateway**:
- New crate or module: gateway calls SpiceDB `CheckPermission` via gRPC (tonic client)
- Replace role-string checks in `authz.rs` with SpiceDB relationship checks
- On sandbox creation: `WriteRelationship(sandbox:id#owner@user:identity)`
- On permission check: `CheckPermission(sandbox:id, "connect", user:identity)`

---

## Component 2: OpenShift Console Plugin (AuthZed Playground + Policy Management)

Fork `gpu-booking-app-plugin` as the skeleton. The plugin provides:

1. **SpiceDB Schema Editor** — integrated AuthZed Playground (WASM, runs in-browser)
2. **Relationship Manager** — CRUD for platform access relationships
3. **Policy Dashboard** — view/propose/approve sandbox network policies
4. **Permission Tester** — live CheckPermission against the cluster's SpiceDB

### Frontend (React + PatternFly v6)

**Pages** (replacing GPU booking pages):

| Route | Component | Purpose |
|---|---|---|
| `/platform-auth/playground` | PlaygroundPage | Embedded AuthZed Playground (schema + relationships + checks) |
| `/platform-auth/relationships` | RelationshipsPage | Browse/create/delete SpiceDB relationships for the cluster |
| `/platform-auth/policies` | PoliciesPage | View sandbox network policies, propose changes, approve proposals |
| `/platform-auth/admin` | AdminPage | Schema versioning, audit log, SpiceDB health |
| `/platform-auth/help/:topic?` | HelpPage | Reuse existing help system with new docs |

**Playground integration approach**:
- The AuthZed Playground (`ghcr.io/authzed/spicedb-playground`) runs SpiceDB via WASM in-browser — no server needed for schema editing/testing
- **iframe** to self-hosted playground instance (deployed as a separate pod, exposed via Route)
- Connect "Apply to Cluster" button that pushes validated schema to the real SpiceDB via the Go backend

### Backend (Go)

**Reuse from gpu-booking-app-plugin**:
- Auth middleware (TokenReview + SubjectAccessReview) — works as-is
- TLS setup (service-serving certs) — works as-is
- Health checks, rate limiting — works as-is
- Helm chart structure — works with relabeling

**New API endpoints**:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/schema` | Read current SpiceDB schema |
| POST | `/api/schema` | Write/update SpiceDB schema |
| GET | `/api/relationships` | List relationships (filtered) |
| POST | `/api/relationships` | Write relationships |
| DELETE | `/api/relationships` | Delete relationships |
| POST | `/api/permissions/check` | Check permission (resource, permission, subject) |
| GET | `/api/policies` | List sandbox policies (from OpenShell gateway) |
| POST | `/api/policies/propose` | Submit policy proposal |
| POST | `/api/policies/approve` | Approve policy proposal |
| GET | `/api/catalogs` | List Trino catalogs + access control |
| POST | `/api/catalogs/grant` | Grant user/org access to a catalog |

**Go dependencies to add**:
```go
github.com/authzed/authzed-go  // SpiceDB client
github.com/authzed/grpcutil    // gRPC helpers
```

### Helm Chart

Based on `gpu-booking-app-plugin/chart/`, renamed and reconfigured:
- New values: `spicedb.endpoint`, `spicedb.token`, `openshell.endpoint`
- ConsolePlugin CR: update name, display name, proxy routes
- RBAC: keep TokenReview/SubjectAccessReview, add SpiceDB secret read

---

## Component 3: Data Lakehouse (Trino on OpenShift)

Deploy using `~/git/trino-chart`. The chart already supports OpenShift (non-root, SCC-compliant, Route support).

**Stack**: Trino coordinator + workers → Iceberg tables → Nessie catalog → MinIO S3

**Deployment steps**:

```bash
# 1. Namespaces
oc create ns trino
oc create ns minio

# 2. MinIO (S3 backend)
oc apply -k ~/git/openshift-minio/overlays/cluster-dev

# 3. Nessie (Iceberg catalog)
oc apply -f ~/git/trino-chart/nessie/ -n trino

# 4. Secrets
oc create secret generic trino-credentials -n trino \
  --from-literal=S3_ACCESS_KEY=minio \
  --from-literal=S3_SECRET_KEY=minio1234

# 5. Trino
helm install trino ~/git/trino-chart/trino -n trino \
  -f custom-values.yaml
```

**Access control integration with SpiceDB**:
- Model Trino catalogs as SpiceDB `catalog` objects
- `catalog:lakehouse#reader@user:alice` → Trino access-control rules.json grants `read-only`
- Console plugin "Grant Catalog Access" writes SpiceDB relationship only (stateless plugin)
- **Reconciliation controller** watches SpiceDB relationships and regenerates Trino access-control ConfigMap
- Trino's `accessControl.refreshPeriod: 60s` picks up changes without restart

---

## Component 4: Agent Deployment via OpenShell

Deploy an agent (Claude, Hermes, or OpenClaw) in an OpenShell sandbox with policy-governed access to the Trino lakehouse.

**Sandbox policy** (what the agent can access):
```yaml
version: 1
network_policies:
  trino_lakehouse:
    endpoints:
      - host: trino.trino.svc.cluster.local
        port: 8080
        protocol: rest
        enforcement: enforce
        rules:
          - allow:
              method: POST
              path: "/v1/statement"
          - allow:
              method: GET
              path: "/v1/statement/**"
          - allow:
              method: DELETE
              path: "/v1/statement/**"
    binaries:
      - path: /usr/bin/curl
      - path: /usr/bin/python3*
      - path: /usr/local/bin/trino

  # Optional: allow agent to call inference endpoint
  inference:
    endpoints:
      - host: inference.local
        port: 8080
```

**SpiceDB authorization** (who can deploy this agent):
```
sandbox:agent-trino-demo#owner@user:mike
sandbox:agent-trino-demo#organization@organization:engineering
sandbox:agent-trino-demo#allowed_catalogs@catalog:lakehouse
```

**Deployment flow**:
1. User opens console plugin → "Deploy Agent" workflow
2. Plugin checks `SpiceDB: CheckPermission(user, "manage", organization)` → authorized?
3. Plugin creates sandbox via OpenShell gateway API
4. Gateway checks `SpiceDB: CheckPermission(user, "connect", sandbox)` → allowed
5. Sandbox starts with OPA policy restricting network to Trino endpoint
6. Agent runs inside sandbox, queries lakehouse via Trino SQL
7. All access logged via OCSF events

**Console plugin integration**:
- "Sandbox Policies" page shows active agent sandboxes + their network policies
- "Catalog Access" column shows which SpiceDB catalogs the sandbox can reach
- Admin can grant/revoke catalog access, which updates both SpiceDB relationships and sandbox policy

---

## Implementation Phases

### Phase 1: Foundation (SpiceDB + OpenShell on OpenShift)
1. Deploy SpiceDB on OpenShift using existing manifests from `~/git/mcp-for-public-health/deploy/spicedb/` (operator + PostgreSQL)
2. Write initial ZED schema (user, org, provider, sandbox, catalog)
3. Deploy OpenShell on OpenShift per NVIDIA docs (privileged SCC, TLS via cert-manager)
4. Prototype: Rust tonic client calling SpiceDB from gateway (proof of concept, not wired into authz.rs yet)

### Phase 2: Console Plugin
1. Fork `gpu-booking-app-plugin` → `openshell-authz-plugin`
2. Strip GPU booking UI/backend, keep shell (auth, Helm, console registration)
3. Add Go SpiceDB client (authzed-go), implement schema/relationship/check API endpoints
4. Build Relationships page (PatternFly table + create modal)
5. Embed AuthZed Playground (iframe to self-hosted `ghcr.io/authzed/spicedb-playground` initially)
6. Build Policies page (read from OpenShell gateway API)

### Phase 3: Data Lakehouse
1. Deploy MinIO + Nessie + Trino on OpenShift using trino-chart
2. Model Trino catalogs in SpiceDB schema
3. Build "Catalog Access" management in console plugin
4. Build reconciliation controller: watches SpiceDB catalog relationships → generates Trino access-control ConfigMap

### Phase 4: Agent + End-to-End (**COMPLETE** — 2026-06-14)
1. ~~Deploy Hermes gateway on OpenShift via Helm chart~~ → Deployed as **OpenShell sandbox** instead (Landlock + OPA isolation)
2. ~~Create three Hermes profiles~~ → Three profiles baked into `quay.io/eformat/hermes-openshell:latest` (`retail-finance`, `retail-sales`, `retail-ops`)
3. ~~Deploy three SpiceDB-aware MCP servers~~ → Three MCP server deployments (`retail-finance-mcp`, `retail-sales-mcp`, `retail-ops-mcp`) with SpiceDB `CheckPermission` before Trino queries
4. ~~Console plugin: admin manages SpiceDB relationships~~ → Console plugin deployed at `openshell-authz` namespace
5. ~~End-to-end demo~~ → Working: OAuth login → profile selection → agent queries → SpiceDB permission check → Trino query → formatted results

**Implementation details (Phase 4)**:
- OpenShell gateway patched with RFC 8441 (HTTP/2 WebSocket extended CONNECT) — `quay.io/eformat/openshell-gateway:0.0.62-h2ws`
- Sandbox architecture: Hermes Gateway (:18642) + Dashboard (:9119, gated OIDC) inside network namespace
- Hermes OIDC login via Keycloak (realm `prelude-m6wl4-vs9lb`, client `hermes-dashboard`)
- API key injected via `env` command on `openshell sandbox create` (no secrets in image)
- OPA policy controls all sandbox network egress (MCP only — Trino and SpiceDB removed from sandbox policy)
- See `examples/retail/README.md` for full architecture diagrams (Mermaid)

### Phase 5: Zero-Trust Identity — Kagenti + AuthBridge (**COMPLETE** — 2026-06-17)
1. ~~Deploy Kagenti infrastructure~~ → ZTWIM/SPIRE operator, Kagenti operator, SPIFFE trust domain `retail-demo`
2. ~~MCP servers with AuthBridge~~ → Envoy sidecar (proxy-init, spiffe-helper, client-registration, envoy-proxy) on all 3 MCP servers
3. ~~Hermes token forwarding~~ → Dashboard auth proxy holds token in memory, forwards MCP requests with Authorization header
4. ~~AuthBridge JWT validation~~ → Inbound JWT validated via Keycloak JWKS, no JWT = 401
5. ~~Token refresh~~ → In-process refresh loop in dashboard, rotates access token before 5-min expiry
6. ~~Keycloak token exchange~~ → Configured and tested (preferred_username survives exchange), not yet active on inbound path
7. ~~OPA hardening~~ → Per-sandbox policies: each sandbox can ONLY reach its own MCP server
8. ~~CTF document~~ → `examples/retail/CAPTURE_THE_FLAG.md` with 7 Dune-themed trials
9. ~~Dashboard auth proxy~~ → Token never on disk, `PR_SET_DUMPABLE=0` blocks `/proc/PID/mem` reads, `ptrace_scope=1` prevents sibling process ptrace
10. ~~sqlglot SQL parsing~~ → Replaced regex-based table extraction with AST parser (Trino dialect), blocks information_schema and cross-schema access

**Implementation details (Phase 5)**:
- MCP server app on port 8080 (authbridge-envoy hardcodes ext_proc gRPC on 9090)
- Envoy inbound listener on :15124, routes to static `local_app` cluster on :8080
- K8s Service targetPort changed to 15124 (OVN-K bypasses pod iptables for Service VIP traffic)
- Port 443 excluded from outbound interception (authbridge needs Keycloak JWKS)
- Token exchange Keycloak setup: `retail-mcp` client, `retail-mcp-aud` scope, `spiffe-mcp-aud` scope on hermes-dashboard
- Demo script: `examples/retail/deploy/demo-zero-trust.sh`
- Trino Query UI: `examples/retail/deploy/trino-query-ui-chart/`
- Dashboard auth proxy: Kagenti-inspired pattern for OpenShell single-container sandboxes. Dashboard process holds OIDC token in memory, runs HTTP proxy on `:8889`, adds Authorization header to MCP requests. Gateway/agent sends plain HTTP to `localhost:8889`. Token never touches disk. `PR_SET_DUMPABLE=0` + `ptrace_scope=1` prevent memory reads by sibling processes.
- Per-sandbox OPA: `sed` generates per-department policy at deploy time from `policy-retail.yaml` template — only that department's MCP server is allowed. Cross-department MCP traffic blocked at network level.
- SQL parsing: sqlglot AST parser (Trino dialect) replaces regex. Validates every `Table` node's catalog and schema. Fails closed on parse errors. Requires at least one in-scope table reference.

---

## Key Decisions (Resolved 2026-06-13)

1. **Playground embedding**: **iframe** to self-hosted `ghcr.io/authzed/spicedb-playground`. Faster to ship; can extract components later if needed.

2. **SpiceDB ↔ Trino sync**: **Controller** watches SpiceDB relationships and reconciles Trino's access-control ConfigMap. Not direct plugin regeneration — keeps the console plugin stateless and the sync reliable.

3. **Agent framework**: **Hermes for all three departments**. One Hermes gateway with three profiles (`retail-finance`, `retail-sales`, `retail-ops`), each with its own SOUL.md personality, MCP server config, and user identity. Profiles provide full isolation — separate config, secrets, skills, and sessions per department. Hermes chart at `examples/retail/deploy/hermes-chart/`.

4. **SpiceDB persistence**: **PostgreSQL**. Existing deployment at `~/git/mcp-for-public-health/deploy/spicedb/` — SpiceDB operator + RHEL 9 PostgreSQL 16 + 1Gi PVC + nonroot-v2 SCC binding + operator memory patch (256Mi→512Mi to fix OOMKill).

5. **OpenShell TLS**: **Enabled** via cert-manager (already deployed on cluster). No disabled-TLS eval mode.

### Existing Assets

| Asset | Location | Notes |
|---|---|---|
| SpiceDB operator + PostgreSQL manifests | `~/git/mcp-for-public-health/deploy/spicedb/` | Kustomize overlay, operator SCC fix, memory patch |
| Hermes BYOC Containerfile | `~/git/self-hosted-openshell/Containerfile.hermes` | UBI builder, uv, sandbox user, `/sandbox/.venv` |
| Trino Helm chart | `~/git/trino-chart` | OpenShift-compatible (non-root, SCC, Route) |
| MinIO | `~/git/openshift-minio/overlays/cluster-dev` | Kustomize overlay for dev cluster |
| Console plugin skeleton | `gpu-booking-app-plugin` | Auth middleware, Helm chart, PatternFly v6, console registration |
