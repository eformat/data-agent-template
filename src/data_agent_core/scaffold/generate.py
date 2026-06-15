"""Project scaffold generator — creates a thin domain agent project."""

from __future__ import annotations

from pathlib import Path

from data_agent_core.config.models import DeploymentConfig, DomainConfig
from data_agent_core.deploy.render import render_deploy_tree


def scaffold_project(name: str, output_dir: str = ".") -> Path:
    """Generate a new domain agent project directory."""
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

deployment:
  namespace: {slug}
  model_name: ""
  model_endpoint: ""

system_prompt_file: system_prompt.md
""")

    # system_prompt.md
    prompt_template = Path(__file__).parent.parent / "prompts" / "system_template.md"
    if prompt_template.exists():
        (root / "system_prompt.md").write_text(prompt_template.read_text())
    else:
        (root / "system_prompt.md").write_text(
            f"# {name.replace('-', ' ').title()} Agent\n\nYou are a data agent.\n"
        )

    # Agent app.py
    (root / "agents" / f"{name}-agent" / "app.py").write_text(f'''"""Chainlit agent for {name}."""

from data_agent_core.mlflow.init import init_mlflow
from data_agent_core.config.loader import load_config
from data_agent_core.agent.app import create_agent_app

config = load_config("../../agent-config.yaml")
init_mlflow(experiment_name=config.mlflow_experiment_name)
create_agent_app(config)
''')

    (root / "agents" / f"{name}-agent" / "requirements.txt").write_text(
        "data-agent-core[agent]\n"
    )

    # MCP server.py
    (root / "agents" / f"{name}-mcp-server" / "server.py").write_text(f'''"""MCP server for {name}."""

from data_agent_core.config.loader import load_config
from data_agent_core.mcp.server import create_mcp_server

config = load_config("../../agent-config.yaml")
mcp = create_mcp_server(config)

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=9090)
''')

    (root / "agents" / f"{name}-mcp-server" / "requirements.txt").write_text(
        "data-agent-core[mcp]\n"
    )

    # Evaluation pipeline
    (root / "evaluations" / "pipeline.py").write_text(f'''"""Evaluation pipeline for {name}."""

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
''')

    (root / "evaluations" / "seed_questions.yaml").write_text("""# Evaluation seed questions
# Add domain-specific questions here
seed_questions: []
""")

    # Tests
    (root / "tests" / "conftest.py").write_text(
        "from data_agent_core.testing.fixtures import *  # noqa: F401,F403\n"
    )

    (root / "tests" / "test_tools.py").write_text(f'''"""Tool tests for {name}."""


def test_config_loads():
    # This will fail until agent-config.yaml has real data
    pass
''')

    # Data loading stub
    (root / "scripts" / "load-data.sh").write_text(f"""#!/bin/bash
# Domain-specific data loader for {name}
echo "TODO: Implement data loading for {name}"
""")

    # pyproject.toml
    (root / "pyproject.toml").write_text(f"""[project]
name = "{name}-agent"
version = "0.1.0"
dependencies = ["data-agent-core"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
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

## Deploy to OpenShift

```bash
# Apply manifests and trigger builds
make deploy-all

# Or step by step:
make deploy-common      # secrets, RBAC, DSPA
make deploy-agent       # agent kustomize
make deploy-mcp         # MCP server kustomize
make build              # trigger OpenShift builds
```
""")

    # Render deploy templates (Containerfiles, kustomize, scripts, Makefile)
    config = DomainConfig(
        domain_name=name,
        domain_display_name=name.replace("-", " ").title() + " Agent",
        domain_description=f"Data agent for {name} domain",
        trino_schema=slug,
        mlflow_experiment_name=f"{name}-data-agent",
        mlflow_prompt_name=f"{name}-agent.system",
        mlflow_span_name=f"{slug}_agent",
        deployment=DeploymentConfig(namespace=slug),
    )
    render_deploy_tree(config, root)

    print(f"Scaffolded: {root}")
    return root
