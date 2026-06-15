"""Template rendering for deploy manifests and scripts."""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path
from string import Template
from urllib.parse import urlparse

from data_agent_core.config.models import DomainConfig

TEMPLATES_DIR = Path(__file__).parent / "templates"


def build_template_vars(config: DomainConfig) -> dict[str, str]:
    """Flatten DomainConfig into a string dict for template substitution."""
    d = config.deployment
    namespace = d.namespace or config.domain_name

    s3_host = ""
    if d.s3_endpoint:
        parsed = urlparse(d.s3_endpoint)
        s3_host = parsed.netloc or parsed.path

    return {
        "DOMAIN_NAME": config.domain_name,
        "DOMAIN_DISPLAY_NAME": config.domain_display_name,
        "NAMESPACE": namespace,
        "REPLICAS": str(d.replicas),
        "MODEL_NAME": d.model_name,
        "MODEL_ENDPOINT": d.model_endpoint,
        "TRINO_HOST": d.trino_host,
        "TRINO_PORT": str(d.trino_port),
        "TRINO_CATALOG": config.trino_catalog,
        "TRINO_SCHEMA": config.trino_schema,
        "MLFLOW_TRACKING_URI": d.mlflow_tracking_uri,
        "MLFLOW_WORKSPACE": d.mlflow_workspace or namespace,
        "MLFLOW_EXPERIMENT_NAME": config.mlflow_experiment_name,
        "MLFLOW_PROMPT_NAME": config.mlflow_prompt_name,
        "S3_ENDPOINT": d.s3_endpoint,
        "S3_ENDPOINT_HOST": s3_host,
        "S3_BUCKET": d.s3_bucket,
        "AGENT_CPU_REQUEST": d.agent_resources.cpu_request,
        "AGENT_MEMORY_REQUEST": d.agent_resources.memory_request,
        "AGENT_CPU_LIMIT": d.agent_resources.cpu_limit,
        "AGENT_MEMORY_LIMIT": d.agent_resources.memory_limit,
        "MCP_CPU_REQUEST": d.mcp_resources.cpu_request,
        "MCP_MEMORY_REQUEST": d.mcp_resources.memory_request,
        "MCP_CPU_LIMIT": d.mcp_resources.cpu_limit,
        "MCP_MEMORY_LIMIT": d.mcp_resources.memory_limit,
        "CHAINLIT_PVC_SIZE": d.chainlit_pvc_size,
        "ROUTE_TIMEOUT": d.route_timeout,
        "ROUTE_TLS_TERMINATION": d.route_tls_termination,
        "CHAINLIT_AUTH_SECRET": secrets.token_hex(32),
    }


def render_template(template_path: Path, variables: dict[str, str]) -> str:
    """Render a single template file with variable substitution."""
    return Template(template_path.read_text()).safe_substitute(variables)


def render_deploy_tree(config: DomainConfig, output_dir: Path) -> None:
    """Render all deploy templates into a scaffolded project directory.

    Populates:
      agents/{name}-agent/deploy/   — agent kustomize manifests
      agents/{name}-mcp-server/deploy/ — MCP server kustomize manifests
      deploy/                       — common manifests (DSPA, RBAC, secrets)
      scripts/                      — deploy-all.sh, set-model.sh, register-prompt.sh
      Makefile                      — build/deploy targets
      agents/{name}-agent/Containerfile
      agents/{name}-mcp-server/Containerfile
    """
    name = config.domain_name
    variables = build_template_vars(config)

    mapping = {
        "agent": output_dir / "agents" / f"{name}-agent" / "deploy",
        "mcp-server": output_dir / "agents" / f"{name}-mcp-server" / "deploy",
        "common": output_dir / "deploy",
    }

    for template_subdir, target_dir in mapping.items():
        src_dir = TEMPLATES_DIR / template_subdir
        if not src_dir.is_dir():
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        for template_file in sorted(src_dir.iterdir()):
            if template_file.is_file():
                rendered = render_template(template_file, variables)
                (target_dir / template_file.name).write_text(rendered)

    scripts_src = TEMPLATES_DIR / "scripts"
    scripts_dst = output_dir / "scripts"
    scripts_dst.mkdir(parents=True, exist_ok=True)
    for template_file in sorted(scripts_src.iterdir()):
        if template_file.is_file():
            rendered = render_template(template_file, variables)
            out_path = scripts_dst / template_file.name
            out_path.write_text(rendered)
            out_path.chmod(out_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)

    makefile_tmpl = TEMPLATES_DIR / "Makefile.template"
    if makefile_tmpl.exists():
        rendered = render_template(makefile_tmpl, variables)
        (output_dir / "Makefile").write_text(rendered)

    for container_name, agent_dir_name in [
        ("Containerfile.agent", f"{name}-agent"),
        ("Containerfile.mcp", f"{name}-mcp-server"),
    ]:
        src = TEMPLATES_DIR / container_name
        if src.exists():
            dst = output_dir / "agents" / agent_dir_name / "Containerfile"
            dst.write_text(src.read_text())
