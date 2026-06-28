---
schema_version: 1
id: RAC-KW86NG7TYK79
type: decision
---
# DuckDB Dev Mode with Transparent Trino SQL Rewriting

## Context

Developers building domain agents need to iterate locally without access to Trino, SpiceDB, or MLflow. Copy-pasting a separate "dev" agent would diverge from production. The dev experience MUST be zero-external-dependency while producing agents that deploy to production with no code changes.

## Decision

We use in-memory DuckDB as a drop-in replacement for Trino in dev mode. The DuckDB tool transparently rewrites Trino three-part names (catalog.schema.table) to DuckDB quoted-schema form. Sample data auto-loads on first run via a registry pattern — domain-specific loaders register by name, with NNDSS as the default fallback. Dev mode uses mock SpiceDB (always allows), no MLflow, and admin/admin auth. A `--trino-live` flag allows connecting to real infrastructure while keeping the dev UI.

## Consequences

**Easier:** `data-agent dev` starts in seconds with zero setup. Same agent code runs in dev and production — only config changes. Registry pattern lets each domain bring its own synthetic data.

**Harder:** DuckDB SQL dialect differences may mask bugs that only surface on Trino (date functions, array handling). Sample data may not exercise production edge cases. The `--trino-live` flag creates a hybrid mode that's harder to test.

## Status

Accepted

## Category

Technical

## Alternatives Considered

- **SQLite as dev backend** — rejected because its SQL dialect is further from Trino than DuckDB, and it lacks DuckDB's columnar analytics features.
- **Trino in Docker for dev** — rejected because it requires Docker, takes minutes to start, and adds infrastructure complexity that defeats the zero-dependency goal.
- **Separate dev-only agent code** — rejected because code divergence between dev and production is the exact problem the framework solves.

## Related Requirements

RAC-KW855N11NRJY
