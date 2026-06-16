# data-agent-core

## What This Is

A pip-installable Python framework (`data-agent-core`) for building methodology-aware data agents on Trino/Iceberg with structured reasoning, MLflow tracing, and 7-dimension evaluation. Extracted from two production agents (MLB and NNDSS).

## Quick Start

```bash
# Create venv and install
python3.12 -m venv venv
source venv/bin/activate
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

## MaaS Endpoints (as of 2026-05-29)

- `kimi-k2-6` — confirmed working
- `gemma4` — confirmed working
- `qwen36-27b` — was down (503)
