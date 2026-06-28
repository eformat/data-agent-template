---
schema_version: 1
id: RAC-KW86NFTVNCZY
type: decision
---
# Regex SQL Blocker with Trino Catalog Permissions as Defense-in-Depth

## Context

The agent generates SQL from LLM output and executes it against production Trino/Iceberg lakehouses. An unconstrained LLM could generate INSERT, DROP, DELETE, or other destructive statements. The system MUST guarantee read-only access regardless of prompt injection or LLM misbehavior.

## Decision

We implement a single-regex SQL blocker that rejects 10 write keywords (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE, GRANT, REVOKE) with case-insensitive word-boundary matching. The blocker runs before any database connection is opened. Query results are capped at 1000 rows. Trino catalog-level read-only permissions serve as the defense-in-depth layer.

## Consequences

**Easier:** The entire blocker is one auditable regex line. Same blocker runs in both Trino and DuckDB modes. No complex SQL parsing required.

**Harder:** Regex cannot distinguish keywords in comments or string literals from actual SQL commands — errs on the side of over-blocking. New SQL keywords (UPSERT, REPLACE) require manual addition. Defense-in-depth depends on Trino catalog permissions being configured correctly.

## Status

Accepted

## Category

Technical

## Alternatives Considered

- **SQL AST parsing (sqlglot)** — rejected for the blocker layer because it adds complexity and parse failures could allow statements through. Used separately in the MCP server for scope validation, but the blocker itself stays regex-based for simplicity.
- **Database-level read-only users only** — rejected as the sole defense because it provides no feedback to the agent about why a query failed, and misconfiguration would silently allow writes.
- **LLM prompt instructions ("never write")** — rejected as unreliable; prompt injection can override instructions.

## Related Requirements

RAC-KW855MBS6T21
