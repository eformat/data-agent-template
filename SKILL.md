# Data Agent Builder Skill

Build and deploy methodology-aware data agents on Trino/Iceberg with structured reasoning, MLflow tracing, and 7-dimension evaluation — guided by settled decisions and requirements recorded in the RAC corpus.

## What This Skill Does

Scaffolds a complete data agent project from a domain description and datasets. The generated project includes:
- **Chainlit agent** with LangGraph ReAct reasoning and deterministic confidence cards
- **MCP server** (FastMCP) with JWT identity, SQL scope validation, and enriched tool responses
- **Evaluation pipeline** (KFP) with 4 deterministic + 7 LLM-as-judge scorers
- **MLflow integration** for tracing, prompt registry, and experiment tracking
- **SpiceDB permissions** for fine-grained data access control
- **OpenShift deployment** with kustomize manifests
- **Data platform infrastructure** (Trino, Nessie, MinIO, SpiceDB) via ArgoCD app-of-apps

## Prerequisites

- Python 3.12+
- `pip install data-agent-core[all]`
- For deployment: KUBECONFIG, OpenAI-compatible model endpoint

## Before you build — check settled decisions

This project uses RAC (Requirements As Code) to record settled decisions. Before proposing architecture, making design choices, or changing existing behavior, **check the corpus first** so you don't contradict accepted decisions.

### Using lore MCP tools (preferred)

```
find_decisions("topic")     # find decisions relevant to a topic
get_artifact("RAC-...")     # read the full text of a decision
search_artifacts("query")  # keyword search across all artifacts
get_summary()              # corpus overview: counts, health, attention items
```

### Using the rac CLI

```bash
rac find "topic" rac/                    # search by keyword
rac resolve RAC-KW86NFEZ9KFT rac/       # look up a specific decision
rac index rac/                           # list all artifacts
```

The settled decisions are also listed in CLAUDE.md under "Settled decisions (RAC)" — read those before starting any implementation work.

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

## Capturing new decisions and requirements

When the work surfaces a new architectural choice, constraint, or requirement that will affect future work, capture it in the RAC corpus:

1. **Use `/rac-capture`** to interview and record a new decision or requirement interactively.
2. **Use `/rac-artifacts`** to create, validate, update, or link artifacts directly.
3. **Use `/rac-review`** to audit the corpus and work findings worst-first.

Every captured artifact must pass `rac validate` before the work is done. Accepted decisions should be added to CLAUDE.md under "Settled decisions (RAC)" so future conversations respect them.

## Key Concepts

- **DomainConfig**: Single Pydantic v2 config object driving all factory functions
- **Factory functions**: `create_agent_app(config)`, `create_mcp_server(config)`, `create_eval_pipeline(config)`
- **Enrichment contract**: Every tool response includes methodology, caveats, citations
- **Reasoning rubric**: 7-field structured reasoning extracted from `<reasoning>` XML tags
- **Deterministic confidence**: HIGH/MODERATE/LOW computed from tool trace, not LLM-generated
- **RAC corpus**: Requirements and decisions in `rac/` — the source of truth for what's settled

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
├── rac/                       # Requirements and decisions
│   ├── requirements/          # What the system must do
│   └── decisions/             # How we decided to build it
└── Makefile                   # build, push, deploy, test
```
