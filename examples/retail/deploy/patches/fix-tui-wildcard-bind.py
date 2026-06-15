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

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/opt/hermes/hermes_cli/web_server.py"
    print(f"Patching {path}", file=sys.stderr)

    with open(path, "r") as f:
        source = f.read()

    source = patch_function(source, "_build_gateway_ws_url")
    source = patch_function(source, "_build_sidecar_url")
    source = patch_lifespan_mcp(source)

    with open(path, "w") as f:
        f.write(source)

    print("Done", file=sys.stderr)

if __name__ == "__main__":
    main()
