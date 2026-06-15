"""JSON Schema export for DomainConfig."""

from data_agent_core.config.models import DomainConfig


def get_json_schema() -> dict:
    """Return the JSON Schema for DomainConfig."""
    return DomainConfig.model_json_schema()
