---
schema_version: 1
id: RAC-KW855PE1H3GV
type: requirement
---
# Methodology Awareness — Dataset Metadata and Reasoning Context

## Problem

Raw query results from a data lakehouse are misleading without methodological context. A count of disease cases means nothing without knowing the surveillance type, collection design, case definition, population coverage, and known biases. The agent must provide this context alongside every data response and reason about data limitations.

## Requirements

- [REQ-001] The describe_datasets tool MUST return dataset metadata including: name, key, category, years available, description, key features, and limitations. An optional `topic` parameter MUST filter by category or key substring; "all" or empty returns all datasets.
- [REQ-002] The get_methodology tool MUST return full methodology metadata for a dataset: surveillance_type, collection_design, case_definition, instruments, population_coverage, known_biases, geographic_resolution, temporal_resolution, update_frequency.
- [REQ-003] Dataset name resolution MUST use case-insensitive alias lookup: `config.aliases[dataset_name.lower()]` resolves to the canonical key. If the alias is not found, the tool MUST return an error listing all available dataset keys.
- [REQ-004] Formal display names MUST be resolved from config.formal_names[resolved_key] when available, falling back to the resolved key.
- [REQ-005] Both metadata tools MUST have async variants for the MCP server that return native dicts with additional data_freshness and citation fields.
- [REQ-006] Methodology metadata MUST be embedded in query tool responses (the `methodology` field in the JSON response) so the LLM has context even without explicitly calling get_methodology.
- [REQ-007] The confidence card MUST factor in methodology awareness: HIGH confidence requires both query_trino AND get_methodology tool calls; query_trino alone yields only MODERATE.

## Success Metrics

- Every data response includes methodology context — either from the embedded field or an explicit get_methodology call.
- Unknown dataset names produce clear error messages listing available options, not silent failures.
- Confidence cards correctly distinguish MODERATE (data only) from HIGH (data + methodology).

## Risks

- Methodology metadata is static in the config file; it may drift from the actual data pipeline characteristics over time.
- The LLM may not consistently call get_methodology, relying on the embedded methodology string — which is less detailed.

## Assumptions

- Domain experts populate the methodology section of agent-config.yaml with accurate, current information.
- Each dataset has a unique canonical key and one or more aliases.

## Related Decisions

RAC-KW86NH0JB3MB
