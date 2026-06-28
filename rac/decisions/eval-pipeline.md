---
schema_version: 1
id: RAC-KW86NGT6SKMT
type: decision
---
# KFP Eval Pipeline with 4 Deterministic + 7 LLM Judge Scorers

## Context

Domain agents must be evaluated systematically before deployment. Traditional LLM evals focus on factual accuracy, but data agents also need evaluation of reasoning quality — methodology awareness, scope adherence, causal inference boundaries, confidence calibration. A manual testing approach does not scale across domains or model changes.

## Decision

We build a 5-step Kubeflow Pipeline (setup_mlflow, create_dataset, generate_variants, run_eval, report_results) with 11 scorers: 4 deterministic (keyword match, forbidden content, confidence card presence, response length) and 7 LLM judges evaluating reasoning dimensions. The agent predictor invokes the ReAct agent in-process (no HTTP) with the same tool config as production. SDG Hub generates question variants with an HTTP fallback.

## Consequences

**Easier:** Eval is fully automated and reproducible via KFP. The 7 reasoning dimensions map directly to the agent's design goals (methodology awareness, confidence calibration). Deterministic scorers catch regressions without LLM judge variability.

**Harder:** LLM judges may produce inconsistent YES/NO ratings on nuanced dimensions. SDG Hub availability varies by environment. KFP is a heavyweight dependency — running eval locally requires a KFP instance or manual component invocation.

## Status

Accepted

## Category

Product

## Alternatives Considered

- **Manual testing with a checklist** — rejected because it doesn't scale across domains, model changes, or prompt iterations.
- **Deterministic scorers only** — rejected because reasoning quality (methodology awareness, causal inference) cannot be measured with keyword matching alone.
- **HTTP-based agent invocation in eval** — rejected because in-process invocation is faster, avoids network configuration, and uses the exact same tool configuration as production.

## Related Requirements

RAC-KW855P2N14RS
