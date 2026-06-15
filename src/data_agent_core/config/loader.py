"""YAML config loading and validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from data_agent_core.config.models import (
    DatasetInfo,
    DeploymentConfig,
    DomainConfig,
    EnrichmentConfig,
    MethodologyInfo,
    SeedQuestion,
    StarterQuestion,
)


def load_config(path: str | Path) -> DomainConfig:
    """Load and validate a DomainConfig from a YAML file.

    The YAML structure uses nested sections (domain, data, enrichment, mlflow,
    starters, eval) which are flattened into the DomainConfig fields.
    """
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping, got {type(raw).__name__}")

    domain = raw.get("domain", {})
    data = raw.get("data", {})
    enrichment_raw = raw.get("enrichment", {})
    mlflow_cfg = raw.get("mlflow", {})
    starters_raw = raw.get("starters", [])
    eval_cfg = raw.get("eval", {})
    mcp_cfg = raw.get("mcp", {})
    deploy_cfg = raw.get("deployment", {})

    # Build datasets dict
    datasets = {}
    for ds in data.get("datasets", []):
        key = ds.get("name", ds.get("key", ""))
        datasets[key] = DatasetInfo(**ds)

    # Build methodology dict
    methodology = {}
    for key, meth in data.get("methodology", {}).items():
        methodology[key] = MethodologyInfo(**meth)

    # Build aliases from datasets
    aliases = data.get("aliases", {})
    for ds in data.get("datasets", []):
        for alias_key, alias_val in ds.get("aliases", {}).items():
            aliases[alias_key] = alias_val

    # Load system prompt from file if referenced
    system_prompt = raw.get("system_prompt", "")
    system_prompt_file = raw.get("system_prompt_file", "")
    if system_prompt_file:
        prompt_path = path.parent / system_prompt_file
        if prompt_path.exists():
            system_prompt = prompt_path.read_text()

    return DomainConfig(
        domain_name=domain.get("name", ""),
        domain_display_name=domain.get("display_name", ""),
        domain_description=domain.get("description", ""),
        trino_catalog=data.get("trino_catalog", "lakehouse"),
        trino_schema=data.get("trino_schema", ""),
        datasets=datasets,
        methodology=methodology,
        aliases=aliases,
        formal_names=data.get("formal_names", {}),
        enrichment=EnrichmentConfig(**enrichment_raw) if enrichment_raw else EnrichmentConfig(),
        computed_statistics=data.get("computed_statistics", []),
        query_tool_docstring=mcp_cfg.get("query_tool_docstring", ""),
        query_result_methodology=mcp_cfg.get("query_result_methodology", ""),
        dataset_source_name=mcp_cfg.get("dataset_source_name", ""),
        dataset_source_url=mcp_cfg.get("dataset_source_url", ""),
        citation_source=mcp_cfg.get("citation_source", ""),
        citation_url=mcp_cfg.get("citation_url", ""),
        system_prompt=system_prompt,
        mlflow_experiment_name=mlflow_cfg.get("experiment_name", ""),
        mlflow_prompt_name=mlflow_cfg.get("prompt_name", ""),
        mlflow_span_name=mlflow_cfg.get("span_name", ""),
        starters=[StarterQuestion(**s) for s in starters_raw],
        step_description=raw.get("step_description", "Querying data..."),
        fallback_reasoning_template=raw.get("fallback_reasoning_template", ""),
        seed_questions=[SeedQuestion(**q) for q in eval_cfg.get("seed_questions", [])],
        deployment=DeploymentConfig(**deploy_cfg) if deploy_cfg else DeploymentConfig(),
    )
