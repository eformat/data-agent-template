"""Tests for DuckDB query tool and sample data."""

import json

from data_agent_core.tools.trino import create_query_duckdb_tool, _rewrite_trino_to_duckdb
from data_agent_core.testing.sample_data import load_sample_data


def test_rewrite_trino_to_duckdb_unquoted():
    sql = "SELECT * FROM lakehouse.nndss.notifications WHERE year = 2023"
    assert _rewrite_trino_to_duckdb(sql, "lakehouse", "nndss") == \
        'SELECT * FROM "lakehouse.nndss".notifications WHERE year = 2023'


def test_rewrite_trino_to_duckdb_already_quoted():
    sql = 'SELECT * FROM "lakehouse.nndss".notifications WHERE year = 2023'
    assert _rewrite_trino_to_duckdb(sql, "lakehouse", "nndss") == sql


def test_rewrite_trino_to_duckdb_join():
    sql = (
        "SELECT n.state FROM lakehouse.nndss.notifications n "
        "JOIN lakehouse.nndss.population p ON n.state = p.state"
    )
    result = _rewrite_trino_to_duckdb(sql, "lakehouse", "nndss")
    assert '"lakehouse.nndss".notifications' in result
    assert '"lakehouse.nndss".population' in result


def test_rewrite_trino_to_duckdb_different_schema():
    sql = "SELECT * FROM lakehouse.mlb.batting"
    assert _rewrite_trino_to_duckdb(sql, "lakehouse", "mlb") == \
        'SELECT * FROM "lakehouse.mlb".batting'


def test_duckdb_tool_trino_sql(agent_config):
    """LLM-generated Trino SQL (unquoted) works against DuckDB via auto-rewrite."""
    import duckdb

    agent_config.trino_catalog = "lakehouse"
    agent_config.trino_schema = "nndss"

    tool, conn = create_query_duckdb_tool(agent_config)
    load_sample_data(conn, agent_config)

    result = json.loads(tool.invoke({
        "sql": "SELECT state, notifications FROM lakehouse.nndss.notifications WHERE disease = 'Influenza (laboratory confirmed)' AND year = 2023 ORDER BY notifications DESC"
    }))

    assert result["row_count"] == 8
    assert result["results"][0]["state"] == "NSW"
    conn.close()


def test_duckdb_tool_trino_sql_join(agent_config):
    """Trino-style JOIN with unquoted three-part names works."""
    import duckdb

    agent_config.trino_catalog = "lakehouse"
    agent_config.trino_schema = "nndss"

    tool, conn = create_query_duckdb_tool(agent_config)
    load_sample_data(conn, agent_config)

    result = json.loads(tool.invoke({
        "sql": """
            SELECT n.state, n.notifications, p.population,
                   ROUND(100000.0 * n.notifications / p.population, 1) AS rate_per_100k
            FROM lakehouse.nndss.notifications n
            JOIN lakehouse.nndss.population p ON n.state = p.state AND n.year = p.year
            WHERE n.year = 2023 AND n.disease = 'Influenza (laboratory confirmed)'
            ORDER BY rate_per_100k DESC
        """
    }))

    assert result["row_count"] == 8
    assert "rate_per_100k" in result["results"][0]
    conn.close()


def test_duckdb_tool_select(agent_config):
    tool, conn = create_query_duckdb_tool(agent_config)
    conn.execute('CREATE TABLE test_table (id INT, name VARCHAR)')
    conn.execute("INSERT INTO test_table VALUES (1, 'alice'), (2, 'bob')")

    result = json.loads(tool.invoke({"sql": "SELECT * FROM test_table"}))
    assert result["row_count"] == 2
    assert result["results"][0]["name"] == "alice"
    conn.close()


def test_duckdb_tool_blocks_write(agent_config):
    tool, conn = create_query_duckdb_tool(agent_config)
    result = json.loads(tool.invoke({"sql": "DROP TABLE test"}))
    assert "error" in result
    assert "SELECT" in result["error"]
    conn.close()


def test_duckdb_tool_returns_methodology(agent_config):
    tool, conn = create_query_duckdb_tool(agent_config)
    conn.execute('CREATE TABLE t (x INT)')
    conn.execute('INSERT INTO t VALUES (1)')
    result = json.loads(tool.invoke({"sql": "SELECT * FROM t"}))
    assert "methodology" in result
    assert "caveats" in result
    conn.close()


def test_sample_data_loads(agent_config):
    import duckdb
    conn = duckdb.connect(":memory:")
    load_sample_data(conn, agent_config)

    catalog = agent_config.trino_catalog
    schema = agent_config.trino_schema
    qualified = f"{catalog}.{schema}"

    count = conn.execute(f'SELECT COUNT(*) FROM "{qualified}".notifications').fetchone()[0]
    assert count > 0

    pop_count = conn.execute(f'SELECT COUNT(*) FROM "{qualified}".population').fetchone()[0]
    assert pop_count > 0
    conn.close()


def test_sample_data_query_nndss(agent_config):
    """Test querying sample data with the DuckDB tool — simulates what the agent does."""
    import duckdb

    agent_config.trino_catalog = "lakehouse"
    agent_config.trino_schema = "nndss"

    tool, conn = create_query_duckdb_tool(agent_config)
    load_sample_data(conn, agent_config)

    result = json.loads(tool.invoke({
        "sql": 'SELECT state, notifications FROM "lakehouse.nndss".notifications WHERE disease = \'Influenza (laboratory confirmed)\' AND year = 2023 ORDER BY notifications DESC'
    }))

    assert result["row_count"] == 8
    assert result["results"][0]["state"] == "NSW"
    assert result["results"][0]["notifications"] == 95000
    conn.close()


def test_sample_data_join_population(agent_config):
    """Test per-capita rate query with sample data."""
    import duckdb

    agent_config.trino_catalog = "lakehouse"
    agent_config.trino_schema = "nndss"

    tool, conn = create_query_duckdb_tool(agent_config)
    load_sample_data(conn, agent_config)

    result = json.loads(tool.invoke({
        "sql": '''
            SELECT n.state, n.notifications, p.population,
                   ROUND(100000.0 * n.notifications / p.population, 1) AS rate_per_100k
            FROM "lakehouse.nndss".notifications n
            JOIN "lakehouse.nndss".population p ON n.state = p.state AND n.year = p.year
            WHERE n.year = 2023 AND n.disease = 'Influenza (laboratory confirmed)'
            ORDER BY rate_per_100k DESC
        '''
    }))

    assert result["row_count"] == 8
    assert "rate_per_100k" in result["results"][0]
    conn.close()
