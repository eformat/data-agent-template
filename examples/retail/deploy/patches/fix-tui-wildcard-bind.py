#!/usr/bin/env python3
"""Patch Hermes for sandboxed/containerized deployments.

Patches applied (all scripted, all automated):

1. Normalize 0.0.0.0/:: to 127.0.0.1 in TUI WebSocket URLs.
   When the dashboard binds 0.0.0.0 for gated/OAuth mode, the TUI child
   tries to connect to ws://0.0.0.0:<port> which SSRF protection blocks.

2. Dashboard Auth Proxy — watertight token isolation.
   Starts an HTTP proxy on :8889 inside the dashboard process.
   Holds the OIDC token IN MEMORY ONLY (never writes to disk).
   Adds Authorization header to MCP requests before forwarding upstream.
   Calls PR_SET_DUMPABLE=0 so sibling processes (gateway/agent) cannot
   read the dashboard's /proc/PID/mem, /proc/PID/environ, or /proc/PID/maps.
   Combined with ptrace_scope=1 (default), the gateway process has ZERO
   access to the token. Kagenti-inspired: "Agents never see tokens."

3. OIDC token capture — stores tokens in memory, NOT on disk.
   Patches the self-hosted OIDC plugin to set an in-memory store instead
   of writing to /tmp/hermes-oidc-token. The auth proxy reads from the
   store. No token file ever exists.
"""
import re
import sys

# ── Patch 1: Wildcard bind fix ──────────────────────────────────

WILDCARD_PATCH = '''    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"'''

# ── Patch 2: Dashboard Auth Proxy ───────────────────────────────

AUTH_PROXY_PATCH = '''
    # ── Auth Proxy: token never touches disk ──────────────────
    # Kagenti pattern adapted for OpenShell single-container sandboxes.
    # The dashboard holds the token; the agent/gateway never sees it.
    import ctypes as _ctypes
    try:
        _libc = _ctypes.CDLL("libc.so.6")
        _libc.prctl(4, 0)  # PR_SET_DUMPABLE = 0
    except Exception:
        pass

    import threading, os, http.server
    import json as _json, base64 as _b64, time as _time
    import urllib.request, urllib.parse, urllib.error

    _upstream_url = os.environ.get("MCP_UPSTREAM_URL", "")
    _proxy_port = int(os.environ.get("MCP_PROXY_PORT", "8889"))

    class _TokenStore:
        token = None
        refresh = None
        lock = threading.Lock()

    # Register as a synthetic module so the OIDC plugin (same process)
    # can import it and set tokens without touching the filesystem.
    import sys as _sys
    _ts_mod = type(_sys)("_auth_token_store")
    _ts_mod.store = _TokenStore
    _sys.modules["_auth_token_store"] = _ts_mod

    class _ProxyHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self._proxy()
        def do_GET(self):
            self._proxy()
        def do_PUT(self):
            self._proxy()
        def do_DELETE(self):
            self._proxy()
        def do_PATCH(self):
            self._proxy()
        def do_OPTIONS(self):
            self._proxy()

        def _proxy(self):
            if not _upstream_url:
                self.send_error(502, "MCP_UPSTREAM_URL not configured")
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else None
            target = _upstream_url.rstrip("/") + self.path
            headers = {}
            for key in self.headers:
                k = key.lower()
                if k in ("host", "authorization"):
                    continue
                headers[key] = self.headers[key]
            with _TokenStore.lock:
                tok = _TokenStore.token
            if tok:
                headers["Authorization"] = f"Bearer {tok}"
            req = urllib.request.Request(
                target, data=body, headers=headers, method=self.command
            )
            try:
                resp = urllib.request.urlopen(req, timeout=300)
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding",):
                        continue
                    self.send_header(k, v)
                self.end_headers()
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                for k, v in e.headers.items():
                    if k.lower() in ("transfer-encoding",):
                        continue
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(e.read())
            except Exception as _e:
                try:
                    self.send_error(502, str(_e))
                except Exception:
                    pass

        def log_message(self, format, *args):
            pass

    def _start_proxy():
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", _proxy_port), _ProxyHandler
        )
        server.serve_forever()
    threading.Thread(target=_start_proxy, daemon=True).start()

    # Token refresh loop — rotates the access token before Keycloak
    # 5-min TTL expires. Runs entirely in-process, no file I/O.
    def _refresh_loop():
        kc_url = os.environ.get("HERMES_DASHBOARD_OIDC_ISSUER", "")
        client_id = os.environ.get("HERMES_DASHBOARD_OIDC_CLIENT_ID",
                                    "hermes-dashboard")
        if not kc_url:
            return
        token_endpoint = (kc_url.rstrip("/")
                          + "/protocol/openid-connect/token")
        while True:
            _time.sleep(30)
            with _TokenStore.lock:
                tok = _TokenStore.token
                rt = _TokenStore.refresh
            if not tok or not rt:
                continue
            try:
                parts = tok.split(".")
                payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
                claims = _json.loads(_b64.urlsafe_b64decode(payload))
                ttl = claims.get("exp", 0) - _time.time()
                if ttl > 60:
                    _time.sleep(max(10, ttl - 60))
                    continue
            except Exception:
                pass
            try:
                data = urllib.parse.urlencode({
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": rt,
                    "scope": "openid profile email",
                }).encode()
                req = urllib.request.Request(
                    token_endpoint, data=data,
                    headers={"Accept": "application/json"})
                resp = urllib.request.urlopen(req, timeout=10)
                body = _json.loads(resp.read())
                new_at = body.get("access_token", "")
                new_rt = body.get("refresh_token", rt)
                with _TokenStore.lock:
                    if new_at:
                        _TokenStore.token = new_at
                    if new_rt:
                        _TokenStore.refresh = new_rt
            except Exception:
                _time.sleep(30)
    threading.Thread(target=_refresh_loop, daemon=True).start()

    # MCP discovery — waits for token to arrive, then discovers tools.
    def _mcp_discover():
        for _ in range(120):
            with _TokenStore.lock:
                if _TokenStore.token:
                    break
            _time.sleep(5)
        else:
            return
        _time.sleep(2)
        try:
            from tools.mcp_tool import discover_mcp_tools
            discover_mcp_tools()
        except Exception:
            pass
    threading.Thread(target=_mcp_discover, daemon=True).start()
'''

# ── Patch 3: OIDC token capture (memory-only) ──────────────────

OIDC_TOKEN_CAPTURE_PATCH = '''
        # Store tokens in the dashboard's in-memory auth proxy store.
        # The token NEVER touches the filesystem. The auth proxy (running
        # in this same process) reads from the store and injects into
        # MCP requests. The gateway/agent process has zero access.
        _oidc_at = payload.get("access_token")
        _oidc_rt = payload.get("refresh_token")
        try:
            import _auth_token_store
            with _auth_token_store.store.lock:
                if _oidc_at:
                    _auth_token_store.store.token = _oidc_at
                if _oidc_rt:
                    _auth_token_store.store.refresh = _oidc_rt
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


def patch_lifespan_auth_proxy(source: str) -> str:
    marker = "app.state.event_channels = {}  # dict[str, set]"
    if marker not in source:
        print("  WARNING: could not find _lifespan marker", file=sys.stderr)
        return source
    result = source.replace(marker, marker + AUTH_PROXY_PATCH, 1)
    print("  Patched _lifespan (auth proxy + token refresh + MCP discovery)",
          file=sys.stderr)
    return result


def main():
    ws_path = (sys.argv[1] if len(sys.argv) > 1
               else "/opt/hermes/hermes_cli/web_server.py")

    print(f"Patching {ws_path}", file=sys.stderr)
    with open(ws_path, "r") as f:
        source = f.read()
    source = patch_function(source, "_build_gateway_ws_url")
    source = patch_function(source, "_build_sidecar_url")
    source = patch_lifespan_auth_proxy(source)
    with open(ws_path, "w") as f:
        f.write(source)

    # Patch self-hosted OIDC plugin to capture tokens in memory.
    oidc_path = "/opt/hermes/plugins/dashboard_auth/self_hosted/__init__.py"
    print(f"Patching {oidc_path}", file=sys.stderr)
    try:
        with open(oidc_path, "r") as f:
            oidc_source = f.read()
        marker = ('        return self._session_from_tokens(\n'
                  '            id_token=id_token, refresh_token='
                  'refresh_token, claims=claims\n        )')
        if marker in oidc_source:
            oidc_source = oidc_source.replace(
                marker, OIDC_TOKEN_CAPTURE_PATCH + marker, 1)
            with open(oidc_path, "w") as f:
                f.write(oidc_source)
            print("  Patched OIDC plugin (in-memory token capture)",
                  file=sys.stderr)
        else:
            print("  WARNING: could not find OIDC token marker",
                  file=sys.stderr)
    except FileNotFoundError:
        print("  WARNING: self-hosted OIDC plugin not found",
              file=sys.stderr)

    print("Done", file=sys.stderr)


if __name__ == "__main__":
    main()
