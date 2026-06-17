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
    # Background thread: wait for OIDC token, discover MCP tools, then
    # refresh the access token before it expires (Keycloak 5-min TTL).
    import threading, pathlib, time as _time, json as _json, base64 as _b64
    def _mcp_token_lifecycle():
        token_path = pathlib.Path("/tmp/hermes-oidc-token")
        refresh_path = pathlib.Path("/tmp/hermes-oidc-refresh")
        # Phase 1: wait for login (token file appears)
        for _ in range(120):
            if token_path.exists() and token_path.stat().st_size > 0:
                break
            _time.sleep(5)
        else:
            return
        _time.sleep(2)
        # Phase 2: discover MCP tools
        try:
            from tools.mcp_tool import discover_mcp_tools
            discover_mcp_tools()
        except Exception:
            pass
        # Phase 3: refresh loop — rotate the access token before expiry
        import os
        kc_url = os.environ.get("HERMES_DASHBOARD_OIDC_ISSUER", "")
        client_id = os.environ.get("HERMES_DASHBOARD_OIDC_CLIENT_ID", "hermes-dashboard")
        if not kc_url:
            return
        token_endpoint = kc_url.rstrip("/") + "/protocol/openid-connect/token"
        while True:
            try:
                tok = token_path.read_text().strip()
                parts = tok.split(".")
                payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
                claims = _json.loads(_b64.urlsafe_b64decode(payload))
                ttl = claims["exp"] - _time.time()
                # Refresh when 60s before expiry (or already expired)
                sleep_for = max(10, ttl - 60)
                _time.sleep(sleep_for)
            except Exception:
                _time.sleep(60)
                continue
            # Do the refresh
            try:
                rt = refresh_path.read_text().strip()
                if not rt:
                    continue
                import urllib.request, urllib.parse
                data = urllib.parse.urlencode({
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": rt,
                    "scope": "openid profile email",
                }).encode()
                req = urllib.request.Request(token_endpoint, data=data,
                    headers={"Accept": "application/json"})
                resp = urllib.request.urlopen(req, timeout=10)
                body = _json.loads(resp.read())
                new_at = body.get("access_token", "")
                new_rt = body.get("refresh_token", rt)
                if new_at:
                    token_path.write_text(new_at)
                if new_rt:
                    refresh_path.write_text(new_rt)
            except Exception:
                _time.sleep(30)
    threading.Thread(target=_mcp_token_lifecycle, daemon=True).start()
'''

OIDC_ACCESS_TOKEN_PATCH = '''
        # Write both the access token and refresh token for MCP identity forwarding.
        # Access token: sent by the MCP client on every request (httpx event hook).
        # Refresh token: used by a background thread to rotate the access token
        # before it expires (5-min Keycloak TTL).
        _oidc_at = payload.get("access_token")
        if _oidc_at:
            import pathlib as _pl
            try:
                _pl.Path("/tmp/hermes-oidc-token").write_text(_oidc_at)
            except Exception:
                pass
        _oidc_rt = payload.get("refresh_token")
        if _oidc_rt:
            import pathlib as _pl
            try:
                _pl.Path("/tmp/hermes-oidc-refresh").write_text(_oidc_rt)
            except Exception:
                pass
'''

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
    """Patch mcp_tool.py to inject OIDC token via request event hook.

    A request hook re-reads /tmp/hermes-oidc-token on every HTTP request,
    so the MCP client always sends the latest token even after Keycloak
    refresh (access tokens have a 5-minute TTL).
    """
    marker = 'client_kwargs["headers"] = headers'
    patch = '''# Inject OIDC token for zero-trust identity forwarding.
                # Request hook re-reads the token file on every request so
                # refreshed tokens are picked up automatically.
                import pathlib as _pl
                _oidc_token_path = _pl.Path("/tmp/hermes-oidc-token")
                async def _inject_oidc_token(request):
                    try:
                        _tok = _oidc_token_path.read_text().strip()
                        if _tok:
                            request.headers["Authorization"] = f"Bearer {_tok}"
                    except Exception:
                        pass
                client_kwargs.setdefault("event_hooks", {}).setdefault("request", []).append(_inject_oidc_token)
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

    # Patch self-hosted OIDC plugin to write the real OAuth access token.
    # The token response payload has both id_token and access_token.
    # Hermes only stores id_token — we capture access_token for MCP forwarding.
    oidc_path = "/opt/hermes/plugins/dashboard_auth/self_hosted/__init__.py"
    print(f"Patching {oidc_path}", file=sys.stderr)
    try:
        with open(oidc_path, "r") as f:
            oidc_source = f.read()
        marker = '        return self._session_from_tokens(\n            id_token=id_token, refresh_token=refresh_token, claims=claims\n        )'
        if marker in oidc_source:
            oidc_source = oidc_source.replace(marker, OIDC_ACCESS_TOKEN_PATCH + marker, 1)
            with open(oidc_path, "w") as f:
                f.write(oidc_source)
            print("  Patched self-hosted OIDC plugin (access token capture)", file=sys.stderr)
        else:
            print("  WARNING: could not find OIDC token marker", file=sys.stderr)
    except FileNotFoundError:
        print("  WARNING: self-hosted OIDC plugin not found", file=sys.stderr)

    print("Done", file=sys.stderr)

if __name__ == "__main__":
    main()
