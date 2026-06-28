---
schema_version: 1
id: RAC-KW86NG1N17HB
type: decision
---
# SpiceDB for Centralized Access Control with Permission Insistence

## Context

Multi-tenant lakehouse environments require per-user, per-dataset access control. Hardcoding permissions in the agent is unmaintainable. The LLM may skip permission checks if not forced, creating an authorization gap between what the user can access and what the agent returns.

## Decision

We use SpiceDB as the centralized authorization engine with gRPC + Bearer token auth. The agent enforces permission insistence: if query_trino was called but check_dataset_permission was not, the agent is re-invoked with a forced permission check. All SpiceDB checks are fail-closed — unreachable or unconfigured SpiceDB denies access. The MCP server adds per-table checks via sqlglot SQL parsing as defense-in-depth. Dev mode uses a mock that always allows.

## Consequences

**Easier:** Permission policy is centralized in SpiceDB, not scattered across agent code. Fail-closed default prevents accidental data leaks. Permission insistence catches LLM tool-ordering mistakes. Dev mode works without SpiceDB.

**Harder:** Each table reference requires a separate gRPC round-trip, adding latency. The LLM could theoretically avoid the permission tool despite insistence (MCP per-table checks mitigate this). SpiceDB must be populated with relationships before agents go live.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

- **OPA (Open Policy Agent)** — rejected because SpiceDB's relationship-based model maps directly to dataset/user/permission triples without needing Rego policy language.
- **Trino row-level security** — rejected because it operates at the SQL layer and doesn't integrate with the agent's tool-calling lifecycle or confidence card system.
- **No permission enforcement (trust the LLM prompt)** — rejected as fundamentally insecure; LLM instructions are not a security boundary.

## Related Requirements

RAC-KW855MNTEJG5
