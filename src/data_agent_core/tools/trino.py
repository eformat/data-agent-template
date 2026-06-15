"""Trino query tool factory."""

from __future__ import annotations

import json
import os
import re

from data_agent_core.config.models import DomainConfig
from data_agent_core.tools.sql_blocker import is_blocked


def _rewrite_trino_to_duckdb(sql: str, catalog: str, schema: str) -> str:
    """Rewrite Trino three-part names to DuckDB quoted-schema names.

    Trino SQL: SELECT * FROM lakehouse.nndss.notifications
    DuckDB:    SELECT * FROM "lakehouse.nndss".notifications

    Handles both unquoted (catalog.schema.table) and already-quoted
    ("catalog.schema".table) forms. Only rewrites references matching
    the configured catalog and schema.
    """
    already_quoted = f'"{catalog}.{schema}".'
    if already_quoted in sql:
        return sql

    unquoted = f"{catalog}.{schema}."
    return sql.replace(unquoted, f'"{catalog}.{schema}".')


def create_query_trino_tool(config: DomainConfig):
    """Create a LangChain @tool that executes read-only SQL against Trino.

    The tool's docstring, schema references, methodology note, and caveats
    are all driven by the DomainConfig.
    """
    from langchain_core.tools import tool

    trino_host = os.environ.get("TRINO_QUERY_HOST", "trino")
    trino_port = int(os.environ.get("TRINO_QUERY_PORT", "8080"))
    catalog = config.trino_catalog
    schema = config.trino_schema

    docstring = config.query_tool_docstring or (
        f"Execute a read-only SQL query against the {catalog}.{schema} "
        f"Iceberg lakehouse in Trino. Only SELECT queries allowed."
    )

    methodology = config.query_result_methodology or (
        f"Data sourced from {config.dataset_source_name or config.domain_display_name}. "
        f"Counts reflect reporting/testing practices, not true incidence."
    )

    caveats = config.enrichment.caveats or [
        "Results are from reported/laboratory-confirmed cases only.",
        "Comparisons should account for population size differences.",
    ]

    @tool(description=docstring)
    def query_trino(sql: str) -> str:
        """Execute a read-only SQL query. Only SELECT queries allowed."""
        if is_blocked(sql):
            return json.dumps({"error": "Only SELECT queries allowed."})

        try:
            from trino.dbapi import connect as trino_connect

            conn = trino_connect(
                host=trino_host, port=trino_port, user="admin",
                catalog=catalog, schema=schema,
            )
            cur = conn.cursor()
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchmany(1000)
            conn.close()

            results = [dict(zip(columns, row)) for row in rows]

            return json.dumps({
                "results": results,
                "row_count": len(results),
                "sql_executed": sql,
                "methodology": methodology,
                "caveats": caveats,
            })
        except Exception as exc:
            return json.dumps({"error": str(exc), "sql_executed": sql})
    return query_trino


def create_query_duckdb_tool(config: DomainConfig, db_path: str = ":memory:"):
    """Create a LangChain @tool that executes read-only SQL against DuckDB.

    Drop-in replacement for create_query_trino_tool — same interface and
    JSON response shape, but backed by DuckDB for local development.
    """
    import duckdb
    from langchain_core.tools import tool

    catalog = config.trino_catalog
    schema = config.trino_schema

    docstring = config.query_tool_docstring or (
        f"Execute a read-only SQL query against the {catalog}.{schema} "
        f"data warehouse. Only SELECT queries allowed."
    )

    methodology = config.query_result_methodology or (
        f"Data sourced from {config.dataset_source_name or config.domain_display_name}. "
        f"[DEV MODE — sample data]"
    )

    caveats = config.enrichment.caveats or [
        "Results are from sample data (dev mode).",
    ]

    conn = duckdb.connect(db_path, read_only=False)

    @tool(description=docstring)
    def query_trino(sql: str) -> str:
        """Execute a read-only SQL query. Only SELECT queries allowed."""
        if is_blocked(sql):
            return json.dumps({"error": "Only SELECT queries allowed."})

        sql = _rewrite_trino_to_duckdb(sql, catalog, schema)

        try:
            result = conn.execute(sql)
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = result.fetchmany(1000)

            results = [dict(zip(columns, row)) for row in rows]

            return json.dumps({
                "results": results,
                "row_count": len(results),
                "sql_executed": sql,
                "methodology": methodology,
                "caveats": caveats,
            }, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "sql_executed": sql})

    query_trino.__doc__ = docstring
    query_trino.name = "query_trino"
    return query_trino, conn


def create_query_trino_tool_async(config: DomainConfig):
    """Create an async MCP tool function for query_trino.

    Returns a plain async function (not a LangChain tool) suitable for
    FastMCP @mcp.tool registration.
    """
    trino_host = os.environ.get("TRINO_QUERY_HOST", "trino")
    trino_port = int(os.environ.get("TRINO_QUERY_PORT", "8080"))
    catalog = config.trino_catalog
    schema = config.trino_schema

    methodology = config.query_result_methodology or (
        f"Data sourced from {config.dataset_source_name or config.domain_display_name}."
    )

    caveats = config.enrichment.caveats or []

    async def query_trino(sql: str) -> dict:
        if is_blocked(sql):
            return {
                "results": [],
                "error": "Only SELECT queries are allowed. Write operations are blocked.",
                "data_freshness": {
                    "dataset_name": config.dataset_source_name,
                    "dataset_url": config.dataset_source_url,
                },
            }

        try:
            from trino.dbapi import connect as trino_connect

            conn = trino_connect(
                host=trino_host, port=trino_port, user="admin",
                catalog=catalog, schema=schema,
            )
            cur = conn.cursor()
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchmany(1000)
            conn.close()

            results = [dict(zip(columns, row)) for row in rows]

            return {
                "results": results,
                "columns": columns,
                "row_count": len(results),
                "sql_executed": sql,
                "truncated": len(results) == 1000,
                "methodology": methodology,
                "data_freshness": {
                    "dataset_name": config.dataset_source_name,
                    "dataset_url": config.dataset_source_url,
                },
                "citation": {
                    "source": config.citation_source,
                    "url": config.citation_url,
                },
                "caveats": caveats,
            }

        except Exception as exc:
            return {
                "results": [],
                "error": str(exc),
                "sql_executed": sql,
                "data_freshness": {
                    "dataset_name": config.dataset_source_name,
                    "dataset_url": config.dataset_source_url,
                },
            }

    return query_trino
