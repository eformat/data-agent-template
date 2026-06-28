---
schema_version: 1
id: RAC-KW855MNTEJG5
type: requirement
---
# Permission Enforcement — SpiceDB Access Control

## Problem

Multi-tenant lakehouse environments require per-user, per-dataset access control. The agent must not return data from datasets a user is not authorized to query. Authorization decisions must be made by a centralized policy engine (SpiceDB), not hardcoded in the agent.

## Requirements

- [REQ-001] In production mode, the agent MUST enforce permission insistence: if query_trino was called during a turn but check_dataset_permission was NOT called, the agent MUST be re-invoked with a permission insistence message forcing a permission check before the response is returned.
- [REQ-002] The SpiceDB permission tool MUST check permissions via gRPC with Bearer token auth (SPICEDB_ENDPOINT, SPICEDB_TOKEN env vars) using the relation: resource=dataset:{resource_id}, permission={permission}, subject=user:{subject_id}.
- [REQ-003] The permission tool MUST return structured JSON: `{allowed: bool, subject: str, resource: str, permission: str}`.
- [REQ-004] SpiceDB checks MUST be fail-closed: if the SpiceDB endpoint is unreachable or not configured, the check MUST deny access — never default to allow.
- [REQ-005] In dev mode, a mock permission tool MUST always return `{allowed: true}` to enable local development without a SpiceDB instance.
- [REQ-006] The MCP server MUST check permissions per-table: SQL is parsed with sqlglot, every referenced table is checked individually against SpiceDB, and access is denied if any table check fails.

## Success Metrics

- No query results are returned for datasets the user lacks permission to access.
- Permission insistence fires consistently in production when the LLM skips the permission check.
- Dev mode runs without SpiceDB dependency.

## Risks

- The LLM may find ways to avoid calling check_dataset_permission despite insistence (prompt injection, tool call ordering). The MCP server's per-table check is the defense-in-depth layer.
- SpiceDB latency adds to query response time; each table reference requires a separate gRPC round-trip.

## Assumptions

- SpiceDB is deployed and populated with dataset permission relationships before agents go live.
- The permission model uses a simple resource/permission/subject triple — no hierarchical or conditional policies.

## Related Decisions

RAC-KW86NG1N17HB
