"""MCP server factory — creates a FastMCP server from DomainConfig.

Usage in a domain project:
    from data_agent_core.mcp.server import create_mcp_server
    from data_agent_core.config.loader import load_config
    config = load_config("agent-config.yaml")
    mcp = create_mcp_server(config)
    if __name__ == "__main__":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=9090)
"""

from __future__ import annotations

import json
import os
import re

from data_agent_core.config.models import DomainConfig


def _check_spicedb_permission(user: str, dataset: str, permission: str = "query") -> dict:
    """Check SpiceDB permission for a user on a dataset.

    Returns {"allowed": bool, ...}. If SpiceDB is not configured, allows all.
    """
    endpoint = os.environ.get("SPICEDB_ENDPOINT")
    if not endpoint:
        return {"allowed": True, "note": "SpiceDB not configured — all access allowed"}

    token = os.environ.get("SPICEDB_TOKEN", "averysecretpresharedkey")
    insecure = os.environ.get("SPICEDB_INSECURE", "true").lower() == "true"

    try:
        import grpc
        from authzed.api.v1 import (
            CheckPermissionRequest, CheckPermissionResponse,
            ObjectReference, SubjectReference,
        )
        from authzed.api.v1 import Client as SpiceDBClient

        if insecure:
            channel = grpc.insecure_channel(endpoint)
            call_creds = grpc.metadata_call_credentials(
                lambda context, callback: callback([("authorization", f"Bearer {token}")], None)
            )
            channel = grpc.intercept_channel(channel)
        else:
            channel = grpc.secure_channel(endpoint, grpc.ssl_channel_credentials())

        client = SpiceDBClient.__new__(SpiceDBClient)
        client.init_stubs(channel)

        metadata = [("authorization", f"Bearer {token}")]
        resp = client.CheckPermission(
            CheckPermissionRequest(
                resource=ObjectReference(object_type="dataset", object_id=dataset),
                permission=permission,
                subject=SubjectReference(
                    object=ObjectReference(object_type="user", object_id=user)
                ),
            ),
            metadata=metadata,
        )
        allowed = resp.permissionship == CheckPermissionResponse.PERMISSIONSHIP_HAS_PERMISSION
        return {"allowed": allowed, "user": user, "dataset": dataset, "permission": permission}

    except Exception as exc:
        return {"allowed": False, "error": str(exc), "user": user, "dataset": dataset}


def _extract_tables_from_sql(sql: str, catalog: str, schema: str) -> list[str]:
    """Extract table names from SQL that reference the configured catalog.schema."""
    pattern = rf"{re.escape(catalog)}\.{re.escape(schema)}\.(\w+)"
    return list(set(re.findall(pattern, sql, re.IGNORECASE)))


def create_mcp_server(config: DomainConfig):
    """Create a FastMCP server with domain-configured tools.

    Tools registered:
    - query_trino: Read-only SQL against Trino (with SpiceDB permission check)
    - check_permission: Check if current user can access a dataset
    - describe_datasets: Dataset metadata and characteristics
    - get_methodology: Deep methodology for a specific dataset
    - /health: K8s readiness probe
    """
    from fastmcp import FastMCP

    from data_agent_core.tools.trino import create_query_trino_tool_async
    from data_agent_core.tools.metadata import (
        create_describe_datasets_tool_async,
        create_get_methodology_tool_async,
    )

    current_user = os.environ.get("CURRENT_USER", "anonymous")

    mcp = FastMCP(
        name=f"{config.domain_name}-data-server",
        instructions=config.domain_description,
    )

    raw_query_fn = create_query_trino_tool_async(config)
    describe_datasets_fn = create_describe_datasets_tool_async(config)
    get_methodology_fn = create_get_methodology_tool_async(config)

    query_doc = config.query_tool_docstring or (
        f"Execute a read-only SQL query against the {config.trino_catalog}.{config.trino_schema} "
        f"Iceberg lakehouse in Trino. Only SELECT queries allowed."
    )

    async def query_trino(sql: str) -> dict:
        tables = _extract_tables_from_sql(sql, config.trino_catalog, config.trino_schema)

        for table in tables:
            check = _check_spicedb_permission(current_user, table)
            if not check.get("allowed"):
                return {
                    "error": f"Permission denied: user '{current_user}' does not have query access to dataset '{table}'",
                    "permission_check": check,
                    "sql_executed": sql,
                }

        return await raw_query_fn(sql)

    mcp.tool(description=query_doc)(query_trino)

    async def check_permission(dataset: str, permission: str = "query") -> dict:
        """Check if the current user has permission to access a dataset via SpiceDB."""
        return _check_spicedb_permission(current_user, dataset, permission)

    mcp.tool(description=f"Check if user '{current_user}' has permission to access a dataset.")(check_permission)

    mcp.tool(description=(
        f"Describe and compare {config.domain_display_name} datasets available for a topic."
    ))(describe_datasets_fn)

    mcp.tool(description=(
        f"Retrieve detailed methodology for a specific {config.domain_display_name} dataset."
    ))(get_methodology_fn)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request):
        from starlette.responses import JSONResponse
        return JSONResponse({
            "status": "ok",
            "user": current_user,
            "spicedb": os.environ.get("SPICEDB_ENDPOINT", "not configured"),
        })

    return mcp
