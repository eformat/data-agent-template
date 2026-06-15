"""Dataset description and methodology tool factories."""

from __future__ import annotations

import json

from data_agent_core.config.models import DomainConfig


def create_describe_datasets_tool(config: DomainConfig):
    """Create a LangChain @tool that lists available datasets."""
    from langchain_core.tools import tool

    @tool
    def describe_datasets(topic: str = "") -> str:
        """List available datasets and their characteristics.

        Args:
            topic: Optional filter (e.g., 'respiratory', 'foodborne', or 'all').
        """
        topic_lower = topic.strip().lower() if topic else "all"

        datasets = {}
        for key, ds in config.datasets.items():
            if topic_lower in ("all", ""):
                datasets[key] = ds
            elif topic_lower in ds.category or topic_lower in key:
                datasets[key] = ds

        return json.dumps({
            "datasets": [
                {
                    "name": ds.formal_name or ds.name,
                    "key": key,
                    "category": ds.category,
                    "years": ds.years_available,
                    "description": ds.description,
                    "key_features": ds.key_features,
                    "limitations": ds.limitations,
                }
                for key, ds in datasets.items()
            ],
        })

    return describe_datasets


def create_get_methodology_tool(config: DomainConfig):
    """Create a LangChain @tool that returns methodology for a dataset."""
    from langchain_core.tools import tool

    @tool
    def get_methodology(dataset_name: str) -> str:
        """Get detailed methodology for a specific dataset.

        Args:
            dataset_name: Dataset name or alias.
        """
        resolved = config.aliases.get(dataset_name.strip().lower())
        if not resolved or resolved not in config.methodology:
            available = ", ".join(config.methodology.keys())
            return json.dumps({
                "error": f"Unknown dataset '{dataset_name}'. Available: {available}."
            })

        meth = config.methodology[resolved]
        formal = config.formal_names.get(resolved, resolved)

        return json.dumps({
            "dataset": formal,
            "surveillance_type": "Passive (notification-based)",
            "collection_design": meth.collection_design,
            "case_definition": meth.case_definition,
            "instruments": meth.instruments,
            "population_coverage": meth.population_coverage,
            "known_biases": meth.known_biases,
            "geographic_resolution": meth.geographic_resolution,
            "temporal_resolution": meth.temporal_resolution,
            "update_frequency": meth.update_frequency,
        })

    return get_methodology


def create_describe_datasets_tool_async(config: DomainConfig):
    """Create an async MCP tool function for describe_datasets."""

    async def describe_datasets(topic: str = "") -> dict:
        topic_lower = topic.strip().lower() if topic else "all"

        filtered = {}
        for key, ds in config.datasets.items():
            if topic_lower in ("all", ""):
                filtered[key] = ds
            elif ds.category and topic_lower in ds.category:
                filtered[key] = ds
            elif topic_lower in key:
                filtered[key] = ds

        return {
            "availability": [
                {
                    "dataset": ds.formal_name or ds.name,
                    "key": key,
                    "category": ds.category,
                    "years_available": ds.years_available,
                    "key_features": ds.key_features,
                    "limitations": ds.limitations,
                }
                for key, ds in filtered.items()
            ],
            "methodology": config.query_result_methodology,
            "data_freshness": {
                "dataset_name": config.dataset_source_name,
                "dataset_url": config.dataset_source_url,
            },
            "citation": {
                "source": config.citation_source,
                "url": config.citation_url,
            },
        }

    return describe_datasets


def create_get_methodology_tool_async(config: DomainConfig):
    """Create an async MCP tool function for get_methodology."""

    async def get_methodology(dataset_name: str) -> dict:
        resolved = config.aliases.get(dataset_name.strip().lower())
        if not resolved or resolved not in config.methodology:
            return {
                "methodology_structured": None,
                "terminology_note": (
                    f"'{dataset_name}' could not be mapped to a known dataset. "
                    f"Available: {', '.join(config.methodology.keys())}."
                ),
                "data_freshness": {
                    "dataset_name": config.dataset_source_name,
                    "dataset_url": config.dataset_source_url,
                },
            }

        meth = config.methodology[resolved]
        formal = config.formal_names.get(resolved, resolved)

        return {
            "methodology_structured": {
                "dataset": formal,
                "surveillance_type": "Passive (notification-based)",
                "collection_design": meth.collection_design,
                "case_definition": meth.case_definition,
                "diagnostic_instruments": meth.instruments,
                "population_coverage": meth.population_coverage,
                "known_biases": meth.known_biases,
                "geographic_resolution": meth.geographic_resolution,
                "temporal_resolution": meth.temporal_resolution,
                "update_frequency": meth.update_frequency,
            },
            "methodology": meth.collection_design,
            "data_freshness": {
                "dataset_name": f"{config.dataset_source_name} — {formal}",
                "dataset_url": config.dataset_source_url,
            },
            "citation": {
                "source": config.citation_source,
                "url": config.citation_url,
            },
        }

    return get_methodology
