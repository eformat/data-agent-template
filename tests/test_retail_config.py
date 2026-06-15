"""Tests for retail example configuration loading."""

from pathlib import Path

from data_agent_core.config.loader import load_config


EXAMPLES = Path(__file__).parent.parent / "examples" / "retail"


def test_load_finance_config():
    config = load_config(EXAMPLES / "finance" / "agent-config.yaml")
    assert config.domain_name == "retail-finance"
    assert config.trino_catalog == "finance"
    assert config.trino_schema == "analytics"
    assert "revenue" in config.datasets
    assert "expenses" in config.datasets
    assert "margins" in config.datasets
    assert "forecasts" in config.datasets
    assert len(config.starters) >= 3
    assert len(config.seed_questions) >= 2
    assert config.system_prompt


def test_load_sales_config():
    config = load_config(EXAMPLES / "sales" / "agent-config.yaml")
    assert config.domain_name == "retail-sales"
    assert config.trino_catalog == "sales"
    assert config.trino_schema == "analytics"
    assert "orders" in config.datasets
    assert "pipeline" in config.datasets
    assert "customers" in config.datasets
    assert "acquisition_costs" in config.datasets
    assert len(config.starters) >= 3


def test_load_ops_config():
    config = load_config(EXAMPLES / "operations" / "agent-config.yaml")
    assert config.domain_name == "retail-ops"
    assert config.trino_catalog == "ops"
    assert config.trino_schema == "analytics"
    assert "inventory" in config.datasets
    assert "shipments" in config.datasets
    assert "warehouses" in config.datasets
    assert "returns" in config.datasets
    assert len(config.starters) >= 3


def test_finance_aliases():
    config = load_config(EXAMPLES / "finance" / "agent-config.yaml")
    assert config.aliases["income"] == "revenue"
    assert config.aliases["costs"] == "expenses"
    assert config.aliases["profit margin"] == "margins"
    assert config.aliases["budget"] == "forecasts"


def test_sales_aliases():
    config = load_config(EXAMPLES / "sales" / "agent-config.yaml")
    assert config.aliases["purchases"] == "orders"
    assert config.aliases["deals"] == "pipeline"
    assert config.aliases["clients"] == "customers"
    assert config.aliases["cac"] == "acquisition_costs"


def test_ops_aliases():
    config = load_config(EXAMPLES / "operations" / "agent-config.yaml")
    assert config.aliases["stock"] == "inventory"
    assert config.aliases["deliveries"] == "shipments"
    assert config.aliases["DCs"] == "warehouses"
    assert config.aliases["refunds"] == "returns"


def test_finance_methodology():
    config = load_config(EXAMPLES / "finance" / "agent-config.yaml")
    assert "revenue" in config.methodology
    assert "ERP" in config.methodology["revenue"].collection_design


def test_sales_methodology():
    config = load_config(EXAMPLES / "sales" / "agent-config.yaml")
    assert "orders" in config.methodology
    assert "Salesforce" in config.methodology["orders"].collection_design


def test_ops_methodology():
    config = load_config(EXAMPLES / "operations" / "agent-config.yaml")
    assert "inventory" in config.methodology
    assert "WMS" in config.methodology["inventory"].collection_design
