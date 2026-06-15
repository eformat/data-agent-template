"""Tests for DomainConfig and YAML loading."""

import json
from pathlib import Path

from data_agent_core.config.models import DomainConfig, DatasetInfo, MethodologyInfo
from data_agent_core.config.loader import load_config
from data_agent_core.config.schema import get_json_schema


def test_domain_config_minimal():
    config = DomainConfig(
        domain_name="test",
        domain_display_name="Test Agent",
        domain_description="A test agent.",
    )
    assert config.domain_name == "test"
    assert config.trino_catalog == "lakehouse"


def test_domain_config_full(agent_config):
    assert agent_config.domain_name == "test-domain"
    assert "sample" in agent_config.datasets
    assert "sample" in agent_config.methodology
    assert agent_config.enrichment.geographic_resolution == "State/territory"


def test_json_schema():
    schema = get_json_schema()
    assert "properties" in schema
    assert "domain_name" in schema["properties"]


def test_load_nndss_config():
    config_path = Path(__file__).parent.parent / "examples" / "nndss" / "agent-config.yaml"
    if not config_path.exists():
        return
    config = load_config(config_path)
    assert config.domain_name == "nndss"
    assert "influenza" in config.datasets
    assert "influenza" in config.methodology
    assert len(config.starters) > 0
    assert len(config.seed_questions) > 0


def test_load_mlb_config():
    config_path = Path(__file__).parent.parent / "examples" / "mlb" / "agent-config.yaml"
    if not config_path.exists():
        return
    config = load_config(config_path)
    assert config.domain_name == "mlb"
    assert "batting" in config.datasets
    assert len(config.starters) > 0
