---
schema_version: 1
id: RAC-KW86NFN06TBB
type: decision
---
# Chainlit + LangGraph ReAct with Deterministic Confidence Cards

## Context

Data analysts querying a lakehouse through an LLM need more than raw SQL results — they need methodological context, reasoning transparency, and calibrated confidence signals. A naive chat-over-SQL interface provides none of these, leading to misinterpretation of results. The agent lifecycle MUST enforce structure: authenticate, check permissions, query, reason, score confidence.

## Decision

We build the agent as a Chainlit application with LangGraph ReAct orchestration. Every response gets a deterministic confidence card (HIGH/MODERATE/LOW) derived from the tool trace, not LLM self-assessment. Output cleaning strips think blocks and extracts structured reasoning XML into a 7-field rubric. A timing footer provides latency transparency.

## Consequences

**Easier:** Confidence cards are deterministic and auditable — no LLM hallucination of confidence levels. Reasoning rubric provides structured metadata for eval scoring. Chainlit provides auth, chat history, and UI out of the box.

**Harder:** Tied to Chainlit's rendering quirks (markdown table fixes needed). LLM may not consistently emit `<reasoning>` XML, leaving rubric fields empty. Single-turn ReAct limits complex multi-step analysis.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

- **Streamlit or Gradio UI** — rejected because Chainlit provides built-in auth, chat history persistence, and step-based rendering that would need to be reimplemented.
- **LLM-generated confidence scores** — rejected because they are unreliable and non-deterministic; tool-trace-based scoring is auditable and reproducible.
- **Multi-agent orchestration** — rejected as premature; single ReAct agent handles current use cases and is simpler to trace and evaluate.

## Related Requirements

RAC-KW855M0NC3Y8
