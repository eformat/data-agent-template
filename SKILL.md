# Data Agent Builder Skill

Build and deploy methodology-aware data agents on Trino/Iceberg with structured reasoning, MLflow tracing, and 7-dimension evaluation.

## What This Skill Does

Scaffolds a complete data agent project from a domain description and datasets. The generated project includes:
- **Chainlit agent** with LangGraph ReAct reasoning and 6-step reasoning protocol
- **MCP server** (FastMCP) with enriched tool responses
- **Evaluation pipeline** (KFP) with 4 deterministic + 7 LLM-as-judge scorers
- **MLflow integration** for tracing, prompt registry, and experiment tracking
- **SpiceDB permissions** for fine-grained data access control
- **OpenShift deployment** with kustomize manifests

## Prerequisites

- Python 3.11+
- `pip install data-agent-core[all]`
- For deployment: KUBECONFIG, OpenAI-compatible model endpoint

## Usage

### 1. Scaffold a new project
```bash
data-agent init my-domain
```

### 2. Configure
Edit `my-domain/agent-config.yaml`:
- Add datasets (name, schema, methodology, aliases)
- Write `system_prompt.md` with domain-specific reasoning examples
- Add seed questions for evaluation

### 3. Validate
```bash
cd my-domain
data-agent validate
```

### 4. Develop locally
```bash
data-agent dev
```

### 5. Test
```bash
data-agent test
```

### 6. Build and deploy
```bash
make build
make push
make deploy-all
```

## Key Concepts

- **DomainConfig**: Single Pydantic v2 config object driving all factory functions
- **Factory functions**: `create_agent_app(config)`, `create_mcp_server(config)`, `create_eval_pipeline(config)`
- **Enrichment contract**: Every tool response includes methodology, caveats, citations
- **Reasoning rubric**: 6-step structured reasoning extracted from `<reasoning>` XML tags
- **Deterministic confidence**: HIGH/MODERATE/LOW computed from tool trace, not LLM-generated

## File Structure (Generated Project)

```
my-domain/
├── agent-config.yaml          # THE config file
├── system_prompt.md           # Domain reasoning prompt
├── agents/
│   ├── my-domain-agent/       # Chainlit app (~10 lines)
│   └── my-domain-mcp-server/  # FastMCP server (~10 lines)
├── evaluations/               # KFP pipeline + seed questions
├── tests/                     # Hermetic tests with mock Trino
├── data/                      # Your parquet/CSV files
└── Makefile                   # build, push, deploy, test
```
