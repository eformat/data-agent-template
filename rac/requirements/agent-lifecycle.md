---
schema_version: 1
id: RAC-KW855M0NC3Y8
type: requirement
---
# Agent Lifecycle — Chainlit + LangGraph ReAct Agent

## Problem

Data analysts need a conversational interface to query structured data, but raw SQL results are misleading without methodological context, confidence signals, and reasoning transparency. The agent must enforce a structured lifecycle — authenticate, check permissions, query, reason, score confidence — rather than just forwarding LLM output.

## Requirements

- [REQ-001] The agent MUST run as a Chainlit application with LangGraph ReAct orchestration, supporting both production mode (real Trino, SpiceDB, MLflow) and dev mode (DuckDB, mock auth, no MLflow).
- [REQ-002] Authentication MUST use a password callback. Production reads AUTH_USERNAME/AUTH_PASSWORD env vars; dev mode defaults to admin/admin.
- [REQ-003] The system prompt MUST be loaded from DomainConfig.system_prompt, with {current_user} placeholder replaced by the authenticated username at chat start.
- [REQ-004] The tool list MUST always include query_trino, describe_datasets, and get_methodology. check_dataset_permission is optional (fails silently if import fails).
- [REQ-005] Output cleaning MUST strip `<think>...</think>` blocks and extract `<reasoning>` XML into a structured ReasoningRubric (7 fields: cross_dataset, methodology, scope, causal_inference, geographic, terminology).
- [REQ-006] A deterministic confidence card MUST be appended to every response based on the tool trace: LOW if query_trino was not called, MODERATE if query_trino was called without get_methodology, HIGH if both query_trino and get_methodology were called.
- [REQ-007] A timing footer MUST show tools used, query time, generation time, and total elapsed time. The step name is configurable via config.step_description.
- [REQ-008] Markdown table syntax MUST be fixed for Chainlit rendering (pipe alignment and header separators).

## Success Metrics

- Every agent response includes a visible confidence card (HIGH / MODERATE / LOW).
- Reasoning rubric fields are populated whenever the LLM emits `<reasoning>` XML.
- Response latency breakdown (query vs generation) is visible in the footer.

## Risks

- LLM may not consistently produce `<reasoning>` XML, leaving rubric fields empty.
- Chainlit UI updates may break markdown table fixes or confidence card rendering.

## Assumptions

- LangGraph ReAct is sufficient for single-turn tool orchestration (no multi-agent).
- The LLM supports tool calling via the OpenAI-compatible API (function calling format).

## Related Decisions

RAC-KW86NFN06TBB
