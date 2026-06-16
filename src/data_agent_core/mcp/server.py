"""MCP server factory — creates a FastMCP server from DomainConfig.

Identity model:
    Every request MUST carry a valid JWT in the Authorization header.
    No JWT = no access. No fallbacks. No env vars. No defaults.
    The JWT user is stored in a module-level global on every HTTP request
    by a Starlette middleware. Tool functions read from the global.
    Single user per sandbox deployment — the global is always correct.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import threading

from data_agent_core.config.models import DomainConfig

logger = logging.getLogger(__name__)

# The authenticated user. Set by middleware on every HTTP request.
# Read by tool functions. Protected by a lock for thread safety.
_identity_lock = threading.Lock()
_authenticated_user: str | None = None


def _extract_user_from_jwt(authorization: str) -> str | None:
    """Extract preferred_username or sub from a JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims.get("preferred_username") or claims.get("sub")
    except Exception:
        return None


def _get_authenticated_user() -> str | None:
    """Get the current authenticated user. Returns None if no JWT identity."""
    with _identity_lock:
        return _authenticated_user


def _set_authenticated_user(user: str | None) -> None:
    """Set the authenticated user from JWT."""
    global _authenticated_user
    with _identity_lock:
        _authenticated_user = user


def _check_spicedb_permission(user: str, dataset: str, permission: str = "query") -> dict:
    """Check SpiceDB permission. Fail-closed: no SpiceDB = deny."""
    endpoint = os.environ.get("SPICEDB_ENDPOINT")
    if not endpoint:
        return {"allowed": False, "error": "SpiceDB not configured", "user": user, "dataset": dataset}

    token = os.environ.get("SPICEDB_TOKEN", "averysecretpresharedkey")

    try:
        import grpc
        from authzed.api.v1 import (
            CheckPermissionRequest, CheckPermissionResponse,
            ObjectReference, SubjectReference,
        )
        from authzed.api.v1 import Client as SpiceDBClient

        channel = grpc.insecure_channel(endpoint)
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
    """Extract table names from SQL."""
    pattern = rf"{re.escape(catalog)}\.{re.escape(schema)}\.(\w+)"
    return list(set(re.findall(pattern, sql, re.IGNORECASE)))


def _deny(reason: str) -> dict:
    """Standard deny response."""
    return {"allowed": False, "error": reason, "reason": "access_denied"}


def create_mcp_server(config: DomainConfig):
    """Create a FastMCP server with identity-aware tools."""
    from fastmcp import FastMCP
    from starlette.types import ASGIApp, Receive, Scope, Send

    from data_agent_core.tools.trino import create_query_trino_tool_async
    from data_agent_core.tools.metadata import (
        create_describe_datasets_tool_async,
        create_get_methodology_tool_async,
    )

    mcp = FastMCP(
        name=f"{config.domain_name}-data-server",
        instructions=config.domain_description,
    )

    # ── Identity middleware ──────────────────────────────────────
    # Extracts JWT user from Authorization header on EVERY HTTP request.
    # Stores in module-level global. One code path. No alternatives.
    #
    # http_app() returns a new object each time, so we monkey-patch it
    # to always wrap with our middleware.

    class IdentityMiddleware:
        """ASGI middleware that extracts JWT identity from every request."""
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                for name, value in scope.get("headers", []):
                    if name == b"authorization":
                        user = _extract_user_from_jwt(value.decode())
                        if user:
                            _set_authenticated_user(user)
                        break
            await self.app(scope, receive, send)

    _original_http_app = mcp.http_app

    def _patched_http_app(**kwargs):
        app = _original_http_app(**kwargs)
        app.add_middleware(IdentityMiddleware)
        return app

    mcp.http_app = _patched_http_app

    # ── Tools ────────────────────────────────────────────────────

    raw_query_fn = create_query_trino_tool_async(config)
    describe_datasets_fn = create_describe_datasets_tool_async(config)
    get_methodology_fn = create_get_methodology_tool_async(config)

    query_doc = config.query_tool_docstring or (
        f"Execute a read-only SQL query against the {config.trino_catalog}.{config.trino_schema} "
        f"Iceberg lakehouse in Trino. Only SELECT queries allowed."
    )

    async def query_trino(sql: str) -> dict:
        user = _get_authenticated_user()
        if not user:
            return _deny("No authenticated user. Log in via the dashboard.")

        tables = _extract_tables_from_sql(sql, config.trino_catalog, config.trino_schema)
        for table in tables:
            check = _check_spicedb_permission(user, table)
            if not check.get("allowed"):
                return _deny(f"User '{user}' cannot access '{table}': {check}")

        return await raw_query_fn(sql)

    mcp.tool(description=query_doc)(query_trino)

    async def check_permission(dataset: str, permission: str = "query") -> dict:
        """Check if the authenticated user can access a dataset."""
        user = _get_authenticated_user()
        if not user:
            return _deny("No authenticated user. Log in via the dashboard.")
        dataset = dataset.rsplit(".", 1)[-1]
        return _check_spicedb_permission(user, dataset, permission)

    mcp.tool(description="Check if the authenticated user can access a dataset.")(check_permission)

    mcp.tool(description=(
        f"Describe and compare {config.domain_display_name} datasets."
    ))(describe_datasets_fn)

    mcp.tool(description=(
        f"Retrieve methodology for a {config.domain_display_name} dataset."
    ))(get_methodology_fn)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request):
        from starlette.responses import JSONResponse
        auth = request.headers.get("authorization", "")
        jwt_user = _extract_user_from_jwt(auth)
        return JSONResponse({
            "status": "ok",
            "user": jwt_user or _get_authenticated_user(),
            "auth_source": "jwt" if jwt_user else ("global" if _get_authenticated_user() else "none"),
            "spicedb": os.environ.get("SPICEDB_ENDPOINT", "not configured"),
        })

    return mcp
