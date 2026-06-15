"""Project scaffold generator — creates a thin domain agent project."""

from __future__ import annotations

import os
from pathlib import Path


def scaffold_project(name: str, output_dir: str = ".") -> Path:
    """Generate a new domain agent project directory.

    Creates only domain-specific files — shared code is imported from
    data-agent-core at runtime.
    """
    root = Path(output_dir) / name
    slug = name.replace("-", "_")

    dirs = [
        root / "data",
        root / "agents" / f"{name}-agent" / "deploy",
        root / "agents" / f"{name}-mcp-server" / "deploy",
        root / "evaluations" / "gold_standards",
        root / "tests",
        root / "scripts",
        root / "deploy",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # agent-config.yaml
    (root / "agent-config.yaml").write_text(f"""domain:
  name: {name}
  display_name: "{name.replace('-', ' ').title()} Agent"
  description: "Data agent for {name} domain"

data:
  trino_catalog: lakehouse
  trino_schema: {slug}
  datasets: []
  methodology: {{}}
  aliases: {{}}
  formal_names: {{}}

enrichment:
  geographic_resolution: ""
  unsupported_conclusions: []
  caveats: []

mcp:
  query_tool_docstring: ""
  dataset_source_name: ""
  dataset_source_url: ""
  citation_source: ""
  citation_url: ""

mlflow:
  experiment_name: {name}-data-agent
  prompt_name: {name}-agent.system
  span_name: {slug}_agent

starters:
  - label: "Available data"
    message: "What data do you have available?"

eval:
  seed_questions: []

system_prompt_file: system_prompt.md
""")

    # system_prompt.md
    prompt_template = Path(__file__).parent.parent / "src" / "data_agent_core" / "prompts" / "system_template.md"
    if prompt_template.exists():
        (root / "system_prompt.md").write_text(prompt_template.read_text())
    else:
        (root / "system_prompt.md").write_text(f"# {name.replace('-', ' ').title()} Agent\\n\\nYou are a data agent.\\n")

    # Agent app.py
    (root / "agents" / f"{name}-agent" / "app.py").write_text(f"""\"\"\"Chainlit agent for {name}.\"\"\"

from data_agent_core.mlflow.init import init_mlflow
from data_agent_core.config.loader import load_config
from data_agent_core.agent.app import create_agent_app

config = load_config("../../agent-config.yaml")
init_mlflow(experiment_name=config.mlflow_experiment_name)
create_agent_app(config)
""")

    # Agent requirements.txt
    (root / "agents" / f"{name}-agent" / "requirements.txt").write_text(
        "data-agent-core[agent]\n"
    )

    # Agent Containerfile
    (root / "agents" / f"{name}-agent" / "Containerfile").write_text(f"""FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/.files /app/.chainlit /app/data
USER 1001
EXPOSE 8080
CMD ["chainlit", "run", "app.py", "--port", "8080", "--headless"]
""")

    # MCP server.py
    (root / "agents" / f"{name}-mcp-server" / "server.py").write_text(f"""\"\"\"MCP server for {name}.\"\"\"

from data_agent_core.config.loader import load_config
from data_agent_core.mcp.server import create_mcp_server

config = load_config("../../agent-config.yaml")
mcp = create_mcp_server(config)

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=9090)
""")

    # MCP requirements.txt
    (root / "agents" / f"{name}-mcp-server" / "requirements.txt").write_text(
        "data-agent-core[mcp]\n"
    )

    # MCP Containerfile
    (root / "agents" / f"{name}-mcp-server" / "Containerfile").write_text(f"""FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER 1001
EXPOSE 9090
CMD ["python", "server.py"]
""")

    # Evaluation pipeline
    (root / "evaluations" / "pipeline.py").write_text(f"""\"\"\"Evaluation pipeline for {name}.\"\"\"

from data_agent_core.config.loader import load_config
from data_agent_core.eval.pipeline import create_eval_pipeline

config = load_config("../agent-config.yaml")
pipeline = create_eval_pipeline(config)

if __name__ == "__main__":
    import argparse
    from pathlib import Path
    from kfp import compiler

    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--output-dir", default="pipelines_gen")
    args = parser.parse_args()

    if args.compile:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "{name}-eval-pipeline.yaml"
        compiler.Compiler().compile(pipeline, str(output_file))
        print(f"Pipeline compiled to: {{output_file}}")
""")

    # Seed questions
    (root / "evaluations" / "seed_questions.yaml").write_text("""# Evaluation seed questions
# Add domain-specific questions here
seed_questions: []
""")

    # Tests
    (root / "tests" / "conftest.py").write_text("""from data_agent_core.testing.fixtures import *  # noqa: F401,F403
""")

    (root / "tests" / "test_tools.py").write_text(f"""\"\"\"Tool tests for {name}.\"\"\"

from data_agent_core.config.loader import load_config


def test_config_loads():
    # This will fail until agent-config.yaml has real data
    pass
""")

    # Scripts
    (root / "scripts" / "load-data.sh").write_text(f"""#!/bin/bash
# Domain-specific data loader for {name}
# Load your parquet/CSV files into Trino here.
echo "TODO: Implement data loading for {name}"
""")

    (root / "scripts" / "deploy-all.sh").write_text(f"""#!/bin/bash
set -euo pipefail
# Deployment orchestrator for {name}
echo "TODO: Implement deployment for {name}"
""")

    # Makefile
    (root / "Makefile").write_text(f""".PHONY: build push deploy-all deploy-agent deploy-mcp load-data test eval-compile

REGISTRY ?= quay.io/YOUR_ORG
AGENT_IMAGE ?= $(REGISTRY)/{name}-agent:latest
MCP_IMAGE ?= $(REGISTRY)/{name}-mcp-server:latest

build:
\tpodman build -t $(AGENT_IMAGE) agents/{name}-agent/
\tpodman build -t $(MCP_IMAGE) agents/{name}-mcp-server/

push:
\tpodman push $(AGENT_IMAGE)
\tpodman push $(MCP_IMAGE)

deploy-all:
\tbash scripts/deploy-all.sh

deploy-agent:
\tkubectl apply -k agents/{name}-agent/deploy/

deploy-mcp:
\tkubectl apply -k agents/{name}-mcp-server/deploy/

load-data:
\tbash scripts/load-data.sh

test:
\tdata-agent test

eval-compile:
\tpython evaluations/pipeline.py --compile
""")

    # pyproject.toml
    (root / "pyproject.toml").write_text(f"""[project]
name = "{name}-agent"
version = "0.1.0"
dependencies = ["data-agent-core"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
""")

    # README
    (root / "README.md").write_text(f"""# {name.replace('-', ' ').title()} Agent

Built with [data-agent-core](https://github.com/your-org/data-agent-template).

## Quick Start

1. Edit `agent-config.yaml` with your domain data
2. Add your data files to `data/`
3. Write your `system_prompt.md`
4. Run: `data-agent validate`
5. Run: `data-agent dev`

## Deploy

```bash
make build
make push
make deploy-all
```
""")

    print(f"Scaffolded: {root}")
    return root
