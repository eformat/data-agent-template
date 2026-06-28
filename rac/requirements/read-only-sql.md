---
schema_version: 1
id: RAC-KW855MBS6T21
type: requirement
---
# Read-Only SQL Enforcement

## Problem

The agent has direct SQL access to production Trino/Iceberg lakehouses containing sensitive data. An LLM generating arbitrary SQL could execute destructive operations (DROP TABLE, DELETE, INSERT) that corrupt production data. The system must guarantee read-only access regardless of what the LLM generates.

## Requirements

- [REQ-001] The SQL blocker MUST reject any SQL statement containing INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE, GRANT, or REVOKE keywords (case-insensitive, word-boundary matched).
- [REQ-002] Blocked SQL MUST return an error message to the agent without executing any part of the statement against the database.
- [REQ-003] The blocker MUST use a single regex check (`\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE)\b`, IGNORECASE) so the allowed/blocked boundary is auditable in one line.
- [REQ-004] Query results MUST be limited to 1000 rows maximum. The tool MUST close the Trino connection after each query.
- [REQ-005] The query tool MUST return a structured JSON response: `{results: [], row_count: int, sql_executed: str, methodology: str, caveats: []}` — never raw result sets.
- [REQ-006] The DuckDB dev-mode tool MUST enforce the same SQL blocker and return the same JSON response shape as the Trino tool, plus a dev-mode caveat.

## Success Metrics

- Zero write operations reach Trino in any deployment (dev or production).
- All 10 blocked SQL keywords are tested individually and in combination.

## Risks

- Regex-based blocking could miss edge cases (e.g., SQL comments containing keywords, dynamic SQL via stored procedures). Trino's read-only catalog-level permissions are the defense-in-depth layer.
- New SQL keywords (e.g., UPSERT, REPLACE) may need to be added to the blocklist.

## Assumptions

- Trino catalog-level permissions provide a second layer of write protection beyond the regex blocker.
- 1000 rows is sufficient for analytical queries; the agent can use LIMIT and aggregation for larger datasets.

## Related Decisions

RAC-KW86NFTVNCZY
