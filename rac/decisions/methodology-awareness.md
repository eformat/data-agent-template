---
schema_version: 1
id: RAC-KW86NH0JB3MB
type: decision
---
# Config-Driven Methodology Metadata with Alias Resolution

## Context

Raw lakehouse query results are misleading without methodological context — surveillance type, collection design, case definitions, known biases. Early prototypes returned numbers without context, leading users to draw incorrect conclusions. The agent needs structured methodology metadata that is domain-configurable, not hardcoded.

## Decision

We store methodology metadata in DomainConfig (YAML) with per-dataset entries covering surveillance_type, collection_design, case_definition, instruments, population_coverage, known_biases, geographic_resolution, temporal_resolution, and update_frequency. Two LangChain tools expose this: describe_datasets (filterable catalog) and get_methodology (full detail for one dataset). Dataset names resolve via case-insensitive alias lookup. Methodology is also embedded in query responses. The confidence card factors in methodology: HIGH requires both query_trino AND get_methodology calls.

## Consequences

**Easier:** Domain experts define methodology in YAML — no code changes needed. Alias resolution handles informal dataset names. Confidence card incentivizes the LLM to check methodology before responding. Embedded methodology in query responses provides context even when get_methodology is not explicitly called.

**Harder:** Methodology metadata is static — it may drift from actual data pipeline characteristics. The LLM may rely on the embedded methodology string rather than calling get_methodology, getting less detail. Unknown datasets produce errors that require the user to know the canonical key or an alias.

## Status

Accepted

## Category

Product

## Alternatives Considered

- **Hardcoded methodology per domain agent** — rejected because it prevents the shared-library model and requires code changes to update methodology.
- **Dynamic methodology from a metadata catalog (e.g., OpenMetadata)** — rejected as premature; the domains are small enough that YAML-driven metadata is sufficient, and adding a metadata catalog dependency is not justified yet.
- **No methodology context (just return SQL results)** — rejected because it was the root cause of user misinterpretation in early prototypes.

## Related Requirements

RAC-KW855PE1H3GV
