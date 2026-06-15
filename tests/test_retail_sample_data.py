"""Tests for retail sample data loading and DuckDB queries."""

import json
from pathlib import Path

import duckdb

from data_agent_core.config.loader import load_config
from data_agent_core.testing.sample_data import load_sample_data
from data_agent_core.tools.trino import create_query_duckdb_tool
import data_agent_core.testing.retail_sample_data  # noqa: F401 — registers loaders


EXAMPLES = Path(__file__).parent.parent / "examples" / "retail"


def _make_conn_and_tool(config_path):
    config = load_config(config_path)
    tool, conn = create_query_duckdb_tool(config)
    load_sample_data(conn, config)
    return config, tool, conn


def test_finance_revenue_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "finance" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT region, SUM(revenue_usd_k) as total FROM "finance.analytics".revenue WHERE year = 2024 GROUP BY region ORDER BY total DESC'
    }))
    assert result["row_count"] == 5
    assert result["results"][0]["region"] == "West"
    conn.close()


def test_finance_expenses_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "finance" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT department, SUM(amount_usd_k) as total FROM "finance.analytics".expenses WHERE year = 2024 GROUP BY department ORDER BY total DESC'
    }))
    assert result["row_count"] == 5
    assert result["results"][0]["department"] == "Operations"
    conn.close()


def test_finance_margins_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "finance" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT product_line, gross_margin_pct FROM "finance.analytics".margins WHERE year = 2024 AND quarter = 4 ORDER BY gross_margin_pct DESC'
    }))
    assert result["row_count"] == 5
    assert result["results"][0]["product_line"] == "Apparel"
    conn.close()


def test_finance_forecasts_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "finance" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT region, variance_pct FROM "finance.analytics".forecasts WHERE year = 2024 AND quarter = 4'
    }))
    assert result["row_count"] == 5
    conn.close()


def test_sales_orders_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "sales" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT channel, COUNT(*) as cnt FROM "sales.analytics".orders GROUP BY channel ORDER BY cnt DESC'
    }))
    assert result["row_count"] >= 3
    conn.close()


def test_sales_pipeline_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "sales" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT stage, COUNT(*) as cnt FROM "sales.analytics".pipeline GROUP BY stage ORDER BY cnt DESC'
    }))
    assert result["row_count"] == 5
    conn.close()


def test_sales_customers_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "sales" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT segment, COUNT(*) as cnt, ROUND(AVG(lifetime_value_usd), 2) as avg_ltv FROM "sales.analytics".customers GROUP BY segment'
    }))
    assert result["row_count"] == 4
    conn.close()


def test_sales_acquisition_costs_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "sales" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT channel, AVG(cac_usd) as avg_cac FROM "sales.analytics".acquisition_costs WHERE year = 2024 GROUP BY channel ORDER BY avg_cac'
    }))
    assert result["row_count"] == 4
    conn.close()


def test_ops_inventory_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "operations" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT warehouse, COUNT(*) as sku_count FROM "ops.analytics".inventory GROUP BY warehouse'
    }))
    assert result["row_count"] == 5
    conn.close()


def test_ops_inventory_below_reorder():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "operations" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT sku, warehouse, quantity_on_hand, reorder_point FROM "ops.analytics".inventory WHERE quantity_on_hand < reorder_point'
    }))
    assert result["row_count"] >= 0
    conn.close()


def test_ops_shipments_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "operations" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT carrier, ROUND(AVG(transit_days), 1) as avg_transit FROM "ops.analytics".shipments GROUP BY carrier'
    }))
    assert result["row_count"] == 3
    conn.close()


def test_ops_warehouses_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "operations" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT warehouse_id, utilization_pct FROM "ops.analytics".warehouses WHERE year = 2024 AND month = 12'
    }))
    assert result["row_count"] == 5
    conn.close()


def test_ops_returns_query():
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "operations" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": 'SELECT reason, COUNT(*) as cnt FROM "ops.analytics".returns GROUP BY reason ORDER BY cnt DESC'
    }))
    assert result["row_count"] == 5
    conn.close()


def test_all_schemas_loaded_from_single_config():
    """All three department schemas are loaded regardless of which config is active."""
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "finance" / "agent-config.yaml")
    sales_count = conn.execute('SELECT COUNT(*) FROM "sales.analytics".orders').fetchone()[0]
    ops_count = conn.execute('SELECT COUNT(*) FROM "ops.analytics".inventory').fetchone()[0]
    assert sales_count > 0
    assert ops_count > 0
    conn.close()


def test_trino_sql_rewrite_finance():
    """Unquoted Trino-style SQL is auto-rewritten for DuckDB."""
    config, tool, conn = _make_conn_and_tool(EXAMPLES / "finance" / "agent-config.yaml")
    result = json.loads(tool.invoke({
        "sql": "SELECT region, SUM(revenue_usd_k) as total FROM finance.analytics.revenue WHERE year = 2024 GROUP BY region"
    }))
    assert result["row_count"] == 5
    conn.close()
