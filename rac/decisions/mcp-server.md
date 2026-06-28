---
schema_version: 1
id: RAC-KW86NGE0RV1M
type: decision
---
# FastMCP Server with JWT Identity and SQL Scope Validation

## Context

External clients (IDEs, notebooks, other agents) need programmatic access to the same data tools the Chainlit agent uses. A shared service account would bypass per-user authorization. The MCP protocol provides a standard tool-serving interface, but identity and scope enforcement must be layered on top.

## Decision

We build a FastMCP server exposing four tools (query_trino, check_permission, describe_datasets, get_methodology). Every request MUST carry a JWT — no fallbacks, no defaults, no anonymous access. The server extracts identity from the JWT payload (preferred_username or sub), validates SQL scope with sqlglot (all tables must be within configured catalog.schema), and checks per-table permissions against SpiceDB. All checks are fail-closed.

## Consequences

**Easier:** Same tools available via chat UI and MCP API with identical authorization. sqlglot scope validation prevents out-of-catalog queries before they reach Trino. Stateless server scales horizontally.

**Harder:** JWT validation is signature-blind (base64 decode only) — depends on ingress gateway for signature verification. Thread-safety of the global authenticated user requires careful lock management. sqlglot must handle all SQL patterns the LLM generates.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

- **REST API with API keys** — rejected because MCP is the emerging standard for tool serving to AI clients, and API keys don't carry user identity claims.
- **Shared service account with audit logging** — rejected because it cannot enforce per-user, per-dataset access control.
- **JWT signature verification in the MCP server** — rejected as redundant when an ingress gateway already validates signatures; adding JWKS fetching would increase complexity and latency.

## Related Requirements

RAC-KW855NCJA75B
