"""Tests for mock permission tool."""

import json

from data_agent_core.tools.spicedb import create_mock_permission_tool


def test_mock_permission_always_allows():
    tool = create_mock_permission_tool()
    result = json.loads(tool.invoke({
        "subject_id": "admin",
        "resource_id": "notifications",
        "permission": "query",
    }))
    assert result["allowed"] is True
    assert result["subject"] == "user:admin"
    assert result["resource"] == "dataset:notifications"
    assert result["permission"] == "query"
