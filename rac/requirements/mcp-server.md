---
schema_version: 1
id: RAC-KW855NCJA75B
type: requirement
---
# MCP Server — Identity-Aware Tool Server

## Problem

External clients (IDEs, notebooks, other agents) need programmatic access to the same data tools the Chainlit agent uses — but with per-request identity and authorization, not a shared service account. The MCP server must enforce the same permission model as the agent while exposing tools over the MCP protocol.

## Requirements

- [REQ-001] The MCP server MUST be a FastMCP application exposing four tools: query_trino, check_permission, describe_datasets, and get_methodology.
- [REQ-002] Every request MUST carry a valid JWT in the Authorization header. There MUST be no fallback to env vars, no default user, and no anonymous access.
- [REQ-003] JWT identity extraction MUST parse the Bearer token, base64-decode the payload, and use the `preferred_username` claim (falling back to `sub` if absent). The extracted user MUST be stored thread-safely for the duration of the request.
- [REQ-004] SQL scope enforcement MUST parse the SQL with sqlglot (Trino dialect), extract all table references, and verify every table is within the configured {catalog}.{schema}. Out-of-scope table references MUST be rejected with a ValueError before any query executes.
- [REQ-005] Per-table SpiceDB permission checks MUST be performed after scope validation: each referenced table is checked individually against SpiceDB for the authenticated user. If any table check fails, the entire query is denied.
- [REQ-006] SpiceDB checks in the MCP server MUST be fail-closed: no SpiceDB endpoint configured means deny all queries.
- [REQ-007] A /health endpoint MUST return `{status, user, auth_source, spicedb}` for monitoring and readiness probes.
- [REQ-008] Tool descriptions MUST be customizable from DomainConfig so each domain agent's MCP server reflects domain-specific documentation.

## Success Metrics

- No unauthenticated request returns data — every tool call without a valid JWT is rejected.
- SQL referencing tables outside the configured catalog.schema is blocked before execution.
- /health endpoint is usable as a Kubernetes readiness probe.

## Risks

- JWT validation is signature-blind (base64 decode only) — relies on the ingress/gateway to validate JWT signatures before traffic reaches the MCP server.
- Thread-safety of the global `_authenticated_user` variable under concurrent requests depends on the lock implementation and FastMCP's concurrency model.

## Assumptions

- An ingress gateway or service mesh validates JWT signatures before requests reach the MCP server.
- sqlglot's Trino dialect parser handles all SQL patterns the LLM generates.

## Related Decisions

RAC-KW86NGE0RV1M
