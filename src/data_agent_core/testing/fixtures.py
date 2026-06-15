"""Pytest fixtures for domain agent testing.

Provides mock_trino (DuckDB-backed), mock_spicedb, and agent_config
fixtures for hermetic testing without external dependencies.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from data_agent_core.config.models import (
    DatasetInfo,
    DomainConfig,
    EnrichmentConfig,
    MethodologyInfo,
    StarterQuestion,
)


@pytest.fixture
def agent_config() -> DomainConfig:
    """A minimal DomainConfig for testing."""
    return DomainConfig(
        domain_name="test-domain",
        domain_display_name="Test Domain Agent",
        domain_description="A test data agent for unit testing.",
        trino_catalog="lakehouse",
        trino_schema="test",
        datasets={
            "sample": DatasetInfo(
                name="sample",
                formal_name="Sample Dataset",
                description="Test dataset",
                category="test",
                years_available="2020-2025",
            ),
        },
        methodology={
            "sample": MethodologyInfo(
                collection_design="Test collection design.",
                case_definition="Test case definition.",
                instruments="Test instruments",
                population_coverage="Test population.",
                known_biases=["Test bias"],
                geographic_resolution="State/territory",
            ),
        },
        aliases={"test": "sample", "example": "sample"},
        formal_names={"sample": "Sample Dataset"},
        enrichment=EnrichmentConfig(
            geographic_resolution="State/territory",
            unsupported_conclusions=["Causal claims"],
            caveats=["Test data only."],
        ),
        dataset_source_name="Test Source",
        dataset_source_url="https://example.com",
        citation_source="Test Citation",
        citation_url="https://example.com/cite",
        system_prompt="You are a test data agent.",
        mlflow_experiment_name="test-agent",
        mlflow_prompt_name="test-agent.system",
        mlflow_span_name="test_agent",
        starters=[
            StarterQuestion(label="Test query", message="Show me test data"),
        ],
    )


@pytest.fixture
def mock_spicedb():
    """Mock SpiceDB client that always returns allowed=True."""
    mock = MagicMock()
    mock.CheckPermission.return_value = MagicMock(
        permissionship=2  # PERMISSIONSHIP_HAS_PERMISSION
    )
    return mock


class MockTrinoConnection:
    """DuckDB-backed mock Trino connection for hermetic testing."""

    def __init__(self, tables: dict[str, list[dict]] | None = None):
        self._tables = tables or {}

    def cursor(self):
        return MockTrinoCursor(self._tables)

    def close(self):
        pass


class MockTrinoCursor:
    def __init__(self, tables: dict[str, list[dict]]):
        self._tables = tables
        self._results: list[tuple] = []
        self._columns: list[str] = []

    def execute(self, sql: str):
        for table_name, rows in self._tables.items():
            if table_name.lower() in sql.lower() and rows:
                self._columns = list(rows[0].keys())
                self._results = [tuple(r.values()) for r in rows]
                return
        self._columns = []
        self._results = []

    @property
    def description(self):
        if not self._columns:
            return None
        return [(col,) for col in self._columns]

    def fetchmany(self, size=1000):
        return self._results[:size]


@pytest.fixture
def mock_trino():
    """DuckDB-backed mock Trino connection factory.

    Usage:
        conn = mock_trino({"notifications": [{"year": 2023, "count": 100}]})
    """
    def factory(tables: dict[str, list[dict]] | None = None):
        return MockTrinoConnection(tables)
    return factory
