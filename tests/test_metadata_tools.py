"""Tests for metadata tool factories."""

import json

from data_agent_core.tools.metadata import (
    create_describe_datasets_tool,
    create_get_methodology_tool,
)


def test_describe_datasets(agent_config):
    tool = create_describe_datasets_tool(agent_config)
    result = json.loads(tool.invoke({"topic": "all"}))
    assert "datasets" in result
    assert len(result["datasets"]) > 0
    assert result["datasets"][0]["name"] == "Sample Dataset"


def test_describe_datasets_filter(agent_config):
    tool = create_describe_datasets_tool(agent_config)
    result = json.loads(tool.invoke({"topic": "test"}))
    assert "datasets" in result
    assert len(result["datasets"]) > 0


def test_get_methodology_known(agent_config):
    tool = create_get_methodology_tool(agent_config)
    result = json.loads(tool.invoke({"dataset_name": "test"}))
    assert "collection_design" in result
    assert "Test collection design" in result["collection_design"]


def test_get_methodology_alias(agent_config):
    tool = create_get_methodology_tool(agent_config)
    result = json.loads(tool.invoke({"dataset_name": "example"}))
    assert "collection_design" in result


def test_get_methodology_unknown(agent_config):
    tool = create_get_methodology_tool(agent_config)
    result = json.loads(tool.invoke({"dataset_name": "nonexistent"}))
    assert "error" in result
