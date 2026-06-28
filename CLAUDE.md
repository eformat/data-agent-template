# data-agent-core

## What This Is

A pip-installable Python framework (`data-agent-core`) for building methodology-aware data agents on Trino/Iceberg with structured reasoning, MLflow tracing, and 7-dimension evaluation. Extracted from two production agents (MLB and NNDSS).

## Quick Start

```bash
# Create venv and install
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"

# Run tests (38 pass)
pytest tests/ -v

# Validate example configs
data-agent validate --config examples/nndss/agent-config.yaml
data-agent validate --config examples/mlb/agent-config.yaml

# Run dev mode (needs LLM endpoint)
export MODEL_ENDPOINT="http://maas.apps.ocp.cloud.rhai-tmm.dev/prelude-maas/kimi-k2-6/v1"
export MODEL_NAME="kimi-k2-6"
export OPENAI_API_KEY="<your-key>"
data-agent dev --config examples/nndss/agent-config.yaml --port 8181
# Login: admin / admin
```

## Package Structure

```
src/data_agent_core/
├── config/       — Pydantic v2 DomainConfig + YAML loader + JSON Schema
├── agent/        — Chainlit + LangGraph lifecycle (app.py, dev.py)
├── tools/        — Tool factories (trino, duckdb, metadata, spicedb, sql_blocker)
├── mcp/          — FastMCP server factory
├── mlflow/       — MLflow init (CA bundle, CR mode auth, autolog)
├── prompts/      — System prompt registry with MLflow integration
├── eval/         — KFP pipeline, 4+7 scorers, predictor function
├── testing/      — pytest fixtures (mock_trino, mock_spicedb, sample_data)
├── deploy/       — Containerfile templates
└── scaffold/     — Project generator (data-agent init)
```

## CLI Commands

- `data-agent init <name>` — scaffold a new domain project
- `data-agent validate --config <path>` — validate agent-config.yaml
- `data-agent dev --config <path> --port <port>` — run locally with DuckDB + mock SpiceDB
- `data-agent test` — run pytest
- `data-agent schema` — print JSON Schema for DomainConfig

## Key Design Decisions

- No Jinja2 code generation — domain projects import shared library
- DomainConfig (Pydantic v2) drives all factory functions
- YAML config is human-facing, Python object at runtime
- Three innovations: MCP enrichment contract, reasoning rubric + deterministic confidence card, 7-dimension eval
- Dev mode uses DuckDB (not Trino) with synthetic sample data

## Completed

1. ~~DuckDB schema mapping~~ — auto-rewrites Trino SQL to DuckDB format
2. ~~Deploy templates~~ — kustomize manifests, BuildConfigs, UBI Containerfiles, scripts
3. ~~Full eval pipeline~~ — 5-step KFP pipeline with SDG Hub variants + 11 scorers
4. ~~`--trino-live` flag~~ — connect dev mode to real Trino + SpiceDB
5. ~~pytest plugin entry point~~ — auto-registers fixtures

## MLflow Compatibility

- RHOAI 3.5: tracking URI = `https://mlflow...svc:8443/mlflow`
- RHOAI 3.4: tracking URI = `https://mlflow...svc:8443` (no `/mlflow` suffix)
- Both require `mlflow.set_workspace()` + `store._workspace_support = True` to bypass probe

## Reference Repos

- MLB: `~/git/mcp-for-mlb`
- NNDSS: `~/git/mcp-for-public-health`

## Testing

```bash
make test  # 55 tests, all pass
```

## MaaS Endpoints

- `kimi-k2-6` — confirmed working
- `gemma4` — confirmed working
- `qwen36-27b` — confirmed working

<!-- BEGIN RAC MANAGED BLOCK (digest: f1dab3f6f52a4bf2baebaec440454253f443c7b3698568ede0949f1d518dcc7c) -->
<!-- Managed by `rac export --agent-rules`. Edit decisions in rac/, not here; content outside this block is preserved. -->
## Settled decisions (RAC)

These decisions are already accepted. Do not re-open or contradict them; ask the `lore` MCP tools (`get_artifact`, `search_artifacts`) for the full text before proposing a change that touches one.

- **RAC-KW86NFEZ9KFT** — Single Pydantic v2 DomainConfig Drives All Factory Functions _(Architecture)_
- **RAC-KW86NFN06TBB** — Chainlit + LangGraph ReAct with Deterministic Confidence Cards _(Architecture)_
- **RAC-KW86NFTVNCZY** — Regex SQL Blocker with Trino Catalog Permissions as Defense-in-Depth _(Technical)_
- **RAC-KW86NG1N17HB** — SpiceDB for Centralized Access Control with Permission Insistence _(Architecture)_
- **RAC-KW86NG7TYK79** — DuckDB Dev Mode with Transparent Trino SQL Rewriting _(Technical)_
- **RAC-KW86NGE0RV1M** — FastMCP Server with JWT Identity and SQL Scope Validation _(Architecture)_
- **RAC-KW86NGKYXV2C** — Portable MLflow Init Across RHOAI 3.4 and 3.5 with Graceful Degradation _(Technical)_
- **RAC-KW86NGT6SKMT** — KFP Eval Pipeline with 4 Deterministic + 7 LLM Judge Scorers _(Product)_
- **RAC-KW86NH0JB3MB** — Config-Driven Methodology Metadata with Alias Resolution _(Product)_
- **RAC-KW86NH6F62TY** — Scaffold Generator with Kustomize Deploy Templates from DomainConfig _(Technical)_
<!-- END RAC MANAGED BLOCK -->
