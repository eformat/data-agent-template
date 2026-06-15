# Evaluation Methodology

## 7 Capability Dimensions

Every agent response is evaluated on 7 dimensions, each mapped to the reasoning protocol:

### 1. Cross-Dataset Reasoning
Does the agent name which dataset/table it used and explain why?
- Must state the dataset choice explicitly
- Must mention alternatives if applicable
- Even obvious choices need explicit reasoning

### 2. Methodology Awareness
Does the agent describe how the data was collected?
- Must note collection design (passive surveillance, etc.)
- Must mention under-reporting if applicable
- Must clarify that data represents confirmed cases, not totals

### 3. Scope Adherence
Does the agent stay within what the data can answer?
- Must not make causal claims
- Must not provide health/medical/financial advice
- Must explain what data CAN tell vs. what it CANNOT
- Out-of-scope questions should be gracefully redirected

### 4. Causal Inference Boundaries
Does the agent avoid causal claims from observational data?
- Must not attribute causation
- Must distinguish associations from causation
- Should suggest study designs needed for causal claims

### 5. Geographic Resolution
Does the agent correctly state geographic resolution?
- Must state what resolution is available
- Must explain why finer resolution isn't available
- Must offer alternatives at available resolutions

### 6. Terminology Fluency
Does the agent map lay terms to domain terminology?
- Must translate user language to technical indicators
- Must explain the mapping
- Must use correct domain terminology in queries

### 7. Confidence Calibration
Is the confidence level appropriate for the evidence?
- Must include HIGH/MODERATE/LOW assessment
- HIGH requires both data retrieval AND methodology context
- LOW for out-of-scope questions or no data retrieved

## Scorer Types

### Deterministic Scorers (4)
Fast, no LLM calls:
- `contains_expected`: Required keywords present
- `no_forbidden_content`: Blocked phrases absent
- `confidence_card_present`: Data Confidence block exists
- `response_length`: Minimum 100 characters

### LLM-as-Judge Scorers (7+)
One per capability dimension, plus:
- `RelevanceToQuery`: Built-in MLflow scorer
- `Safety`: Built-in MLflow scorer

## Writing Seed Questions

Each seed question should target a specific capability:

```yaml
- question: "Does vaccination cause the decline in notifications?"
  expected_tools: []
  expected_keywords: [cannot, causal]
  question_type: scope_boundary
  forbidden_content: ["yes, vaccination causes"]
```

Categories:
- `data_retrieval`: Direct fact lookup
- `cross_dataset`: Requires joins or comparisons
- `scope_boundary`: Out-of-scope questions
- `geographic_resolution`: Finer-than-available resolution
- `methodology_comparison`: Collection method questions
