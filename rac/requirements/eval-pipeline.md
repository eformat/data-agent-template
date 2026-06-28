---
schema_version: 1
id: RAC-KW855P2N14RS
type: requirement
---
# Evaluation Pipeline — KFP + 11 Scorers

## Problem

Domain agents must be evaluated systematically before deployment, not just manually tested. Evaluation must cover both factual correctness (did the agent query the right data?) and reasoning quality (did the agent apply methodology, respect scope, calibrate confidence?). The evaluation must be reproducible, automated via Kubeflow Pipelines, and scored across 7 domain-specific reasoning dimensions.

## Requirements

- [REQ-001] The eval pipeline MUST be a 5-step Kubeflow Pipeline: setup_mlflow, create_dataset, generate_variants, run_eval, report_results.
- [REQ-002] Seed questions MUST be sourced from DomainConfig (eval section) with the format: `{inputs: {question}, expectations: {expected_keywords, question_type, forbidden_content}}`.
- [REQ-003] Variant generation MUST use SDG Hub when available, with an HTTP fallback for environments without the SDG dependency. Default: 3 variants per seed question.
- [REQ-004] The agent predictor MUST invoke the LangChain ReAct agent directly (in-process, no HTTP) using the same tool configuration as production, returning the last AI message.
- [REQ-005] 4 deterministic scorers MUST be included: contains_expected (case-insensitive keyword match), no_forbidden_content, confidence_card_present ("data confidence" string presence), response_adequate_length.
- [REQ-006] 7 LLM judge scorers MUST evaluate reasoning dimensions: cross_dataset_reasoning, methodology_awareness, scope_adherence, causal_inference_boundaries, geographic_resolution, terminology_fluency, confidence_calibration.
- [REQ-007] LLM judges MUST use direct HTTP POST to {llm_base_url}/chat/completions with a criterion prompt + question + response, expecting a YES/NO answer.
- [REQ-008] Pipeline parameters MUST include: mlflow_tracking_uri, mlflow_workspace, mlflow_experiment_name, dataset_name, llm_base_url, agent_model, judge_model, trino_host, trino_port, llm_secret_name.
- [REQ-009] The eval pipeline MUST use the same portable MLflow init as the agent (RHOAI 3.4/3.5 compatible) and log all results to the configured MLflow experiment.

## Success Metrics

- Eval pipeline runs end-to-end on KFP with a single `create_eval_pipeline(config)` call.
- All 11 scorers produce numeric scores (0.0-1.0) logged to MLflow for comparison across runs.
- Variant generation produces meaningfully different phrasings of each seed question.

## Risks

- LLM judges may produce inconsistent YES/NO ratings, especially for nuanced dimensions like causal_inference_boundaries.
- SDG Hub availability varies by environment; HTTP fallback quality may differ.

## Assumptions

- A Kubeflow Pipelines instance is available in the deployment environment.
- The judge model is capable of evaluating domain-specific reasoning (not a small/weak model).

## Related Decisions

RAC-KW86NGT6SKMT
