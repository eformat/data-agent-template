---
schema_version: 1
id: RAC-KW855N11NRJY
type: requirement
---
# Dev Mode — Local Development with DuckDB

## Problem

Developers building domain agents need to iterate locally without access to a Trino cluster, SpiceDB instance, or MLflow server. Dev mode must provide a faithful-enough substitute that agents can be built and tested locally, then deployed to production with no code changes.

## Requirements

- [REQ-001] Dev mode MUST use an in-memory DuckDB database as a drop-in replacement for Trino. The agent writes standard Trino SQL; the DuckDB tool transparently rewrites it.
- [REQ-002] Trino three-part names (catalog.schema.table) MUST be rewritten to DuckDB quoted-schema form ("catalog.schema".table). The rewrite MUST be idempotent — already-quoted names MUST pass through unchanged.
- [REQ-003] Sample data MUST be auto-loaded on first run. The loader creates a DuckDB schema matching "{catalog}.{schema}" from the config and populates it with synthetic data.
- [REQ-004] Sample data loading MUST use a registry pattern: domain-specific loaders register by domain_name prefix (e.g., "retail"), with a default NNDSS loader as fallback for unregistered domains.
- [REQ-005] Dev mode MUST use a mock SpiceDB tool that always returns allowed=true, eliminating the SpiceDB dependency for local development.
- [REQ-006] Dev mode MUST NOT require MLflow. No tracing, no prompt registry, no experiment tracking.
- [REQ-007] Auth in dev mode MUST default to admin/admin (no JWT, no external auth provider).
- [REQ-008] The `--trino-live` CLI flag MUST switch dev mode to connect to a real Trino cluster and SpiceDB instance while keeping the dev Chainlit UI.
- [REQ-009] The DuckDB query tool MUST return the same JSON response shape as the Trino tool, with an additional caveat: "Results are from sample data (dev mode)."

## Success Metrics

- `data-agent dev --config <path>` starts a working agent in under 5 seconds with zero external dependencies.
- An agent built and tested in dev mode deploys to production with no code changes — only config changes (endpoint URLs, credentials).

## Risks

- DuckDB SQL dialect differences may mask bugs that only appear on Trino (e.g., date functions, array handling, case sensitivity).
- Sample data may not exercise edge cases present in real datasets.

## Assumptions

- DuckDB's SQL compatibility with Trino is sufficient for the query patterns agents generate.
- Developers have Python 3.12+ and can install the package locally.

## Related Decisions

RAC-KW86NG7TYK79
