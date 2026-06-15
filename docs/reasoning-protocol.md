# Reasoning Protocol

## Why Structured Reasoning?

Data agents that answer from raw query results without context produce misleading answers. The 6-step reasoning protocol forces the agent to consider methodology, scope, and limitations before responding.

## The 6 Steps

### 1. Cross-Dataset Reasoning
**Why:** Users don't always know which table to query. The agent must explicitly choose and justify.

**How to customize:** Add your domain's dataset alternatives and join patterns to the system prompt.

### 2. Methodology Awareness
**Why:** Without understanding how data was collected, the agent can't interpret results correctly. Under-reporting, testing bias, and collection changes all affect interpretation.

**How to customize:** Fill in `methodology` in `agent-config.yaml` with your domain's collection design, instruments, biases, and coverage.

### 3. Scope Adherence
**Why:** Data can answer some questions and not others. The agent must know its boundaries.

**How to customize:** Add `unsupported_conclusions` to `enrichment` in config. Include common out-of-scope question types in seed questions.

### 4. Causal Inference Boundaries
**Why:** Observational data shows associations, not causation. Users often imply causation in questions.

**How to customize:** Include scope_boundary seed questions that test causal inference handling.

### 5. Geographic Resolution
**Why:** Users often request finer resolution than available. The agent must explain limitations and offer alternatives.

**How to customize:** Set `geographic_resolution` in enrichment config.

### 6. Terminology Fluency
**Why:** Users use lay terms; data uses technical terms. The agent must bridge this gap.

**How to customize:** Fill in `aliases` in config to map lay terms to canonical dataset names.

## Output Format

Every response includes:
1. `<reasoning>` XML block with all 6 considerations
2. Data-grounded answer
3. Confidence card (HIGH/MODERATE/LOW — deterministic from tool trace)
4. Data Freshness footer

## Confidence Card Rules

Computed programmatically from the tool trace (`_build_confidence_card()`):
- **HIGH:** `query_trino` + `get_methodology` both called
- **MODERATE:** `query_trino` called (data retrieved, no methodology)
- **LOW:** No data tools called

This is deterministic — not LLM-generated — ensuring consistent, auditable confidence.
