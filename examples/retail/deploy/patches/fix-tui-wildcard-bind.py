#!/usr/bin/env python3
"""Patch Hermes web_server.py for sandboxed/containerized deployments.

Two fixes, both upstream PR candidates:

1. Normalize 0.0.0.0/:: to 127.0.0.1 in TUI WebSocket URLs.
   When the dashboard binds 0.0.0.0 for gated/OAuth mode, the TUI child
   tries to connect to ws://0.0.0.0:<port> which SSRF protection blocks.
   The TUI runs on the same host, so 127.0.0.1 is correct.

2. Auto-discover MCP tools at dashboard startup.
   When gateway and dashboard run as separate processes (NemoClaw pattern),
   only the gateway calls discover_mcp_tools(). The dashboard's agent
   sessions start with 0 MCP tools until /reload-mcp is manually run.
   This patch adds discovery to the dashboard's lifespan hook.
"""
import re
import sys

WILDCARD_PATCH = '''    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"'''

MCP_DISCOVERY_PATCH = '''
    # Auto-discover MCP tools so dashboard agent sessions have them immediately.
    # Without this, MCP tools only appear after manual /reload-mcp.
    try:
        from tools.mcp_tool import discover_mcp_tools
        discover_mcp_tools()
    except Exception:
        pass
'''

TOKEN_FORWARD_PATCH = '\n'.join([
    '',
    '    # Write OIDC access token for MCP identity forwarding',
    '    import pathlib as _pathlib',
    '    _token_path = _pathlib.Path("/tmp/hermes-oidc-token")',
    '    try:',
    '        _token_path.write_text(session.access_token)',
    '    except Exception:',
    '        pass',
    '',
])

def patch_function(source: str, func_name: str) -> str:
    pattern = rf'(def {func_name}\(.*?\n(?:.*?\n)*?    host = getattr\(app\.state, "bound_host", None\))'
    match = re.search(pattern, source)
    if not match:
        print(f"  WARNING: could not find {func_name}", file=sys.stderr)
        return source
    original = match.group(1)
    patched = original + "\n" + WILDCARD_PATCH
    result = source.replace(original, patched, 1)
    print(f"  Patched {func_name}", file=sys.stderr)
    return result

def patch_lifespan_mcp(source: str) -> str:
    marker = "app.state.event_channels = {}  # dict[str, set]"
    if marker not in source:
        print("  WARNING: could not find _lifespan marker", file=sys.stderr)
        return source
    result = source.replace(marker, marker + MCP_DISCOVERY_PATCH, 1)
    print("  Patched _lifespan (MCP auto-discovery)", file=sys.stderr)
    return result

def patch_mcp_token_forward(source: str) -> str:
    """Patch mcp_tool.py to inject OIDC token via static headers.

    The token is read from /tmp/hermes-oidc-token and set as a static header.
    This runs at MCP connection time — the token must exist by then.
    The httpx event_hooks response handler refreshes it on each response
    so it picks up token changes (e.g., after re-login).
    """
    marker = 'client_kwargs["headers"] = headers'
    patch = '''# Inject OIDC token for zero-trust identity forwarding
                import pathlib as _pl
                _oidc_token_path = _pl.Path("/tmp/hermes-oidc-token")
                try:
                    _tok = _oidc_token_path.read_text().strip()
                    if _tok:
                        headers["Authorization"] = f"Bearer {_tok}"
                except Exception:
                    pass
                client_kwargs["headers"] = headers'''
    if marker not in source:
        print("  WARNING: could not find mcp_tool client_kwargs marker", file=sys.stderr)
        return source
    result = source.replace(marker, patch, 1)
    print("  Patched mcp_tool.py (OIDC token in headers)", file=sys.stderr)
    return result

def main():
    ws_path = sys.argv[1] if len(sys.argv) > 1 else "/opt/hermes/hermes_cli/web_server.py"
    mcp_path = sys.argv[2] if len(sys.argv) > 2 else "/opt/hermes/tools/mcp_tool.py"

    print(f"Patching {ws_path}", file=sys.stderr)
    with open(ws_path, "r") as f:
        source = f.read()
    source = patch_function(source, "_build_gateway_ws_url")
    source = patch_function(source, "_build_sidecar_url")
    source = patch_lifespan_mcp(source)
    with open(ws_path, "w") as f:
        f.write(source)

    print(f"Patching {mcp_path}", file=sys.stderr)
    with open(mcp_path, "r") as f:
        mcp_source = f.read()
    mcp_source = patch_mcp_token_forward(mcp_source)
    with open(mcp_path, "w") as f:
        f.write(mcp_source)

    # Patch routes.py to write the OIDC token on BOTH login callback paths.
    # Path 1: redirect-based (clear_pkce_cookie after set_session_cookies)
    # Path 2: SPA JSON-based (set_session_cookies in POST /auth/callback/complete)
    routes_path = ws_path.replace("web_server.py", "dashboard_auth/routes.py")
    print(f"Patching {routes_path}", file=sys.stderr)
    try:
        with open(routes_path, "r") as f:
            routes_source = f.read()
        # Inject token write before both login return points
        count = 0
        for m in ["    clear_pkce_cookie(resp, prefix=_prefix(request))",
                   '    return resp\n\n\n@router.post("/auth/logout"']:
            if m in routes_source:
                routes_source = routes_source.replace(m, TOKEN_FORWARD_PATCH + m, 1)
                count += 1
        if count:
            with open(routes_path, "w") as f:
                f.write(routes_source)
            print(f"  Patched routes.py ({count} login callback paths)", file=sys.stderr)
        else:
            print("  WARNING: could not find routes.py markers", file=sys.stderr)
    except FileNotFoundError:
        print("  WARNING: routes.py not found", file=sys.stderr)

    print("Done", file=sys.stderr)

if __name__ == "__main__":
    main()
