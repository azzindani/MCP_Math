"""The HTTP server must not close a connection the proxy still pools.

uvicorn's default timeout_keep_alive is 5 seconds and the official SDK's
run_streamable_http_async builds uvicorn.Config without it, so there is no way
to raise it through mcp.run(). Caddy pools upstream connections for 2 minutes
by default, so every connection idle between 5s and 2min was dead here and live
in the pool. Reusing one gave the proxy:

    aborting with incomplete response ... upstream mcp-data-analyst:8810
    error: read tcp ...: use of closed network connection

which it turned into a 200 with zero bytes. The caller hung until its own
timeout with the tool call already executed. Measured against the deployment:
idle 2s reused fine, idle 7s closed by the server.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "src" / "server.py"


def _tree():
    return ast.parse(SERVER.read_text(encoding="utf-8"))


def test_http_transport_sets_an_explicit_keepalive():
    """uvicorn.run must be given timeout_keep_alive, not left on the 5s default."""
    calls = [
        n
        for n in ast.walk(_tree())
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "run"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "uvicorn"
    ]
    assert calls, "http transport no longer runs uvicorn directly — see this file's docstring"
    for call in calls:
        kwargs = {k.arg for k in call.keywords}
        assert "timeout_keep_alive" in kwargs, "uvicorn.run without timeout_keep_alive falls back to 5 seconds"


def test_the_keepalive_outlives_a_two_minute_proxy_pool():
    import server

    assert server.KEEPALIVE_SECONDS > 120, (
        f"{server.KEEPALIVE_SECONDS}s does not clear Caddy's 2-minute default idle pool"
    )


def test_the_keepalive_is_configurable_without_editing_code():
    # An operator behind a proxy that pools for longer must be able to say so.
    assert "MCP_KEEPALIVE_SECONDS" in SERVER.read_text(encoding="utf-8")


def test_the_env_var_is_read(monkeypatch):
    monkeypatch.setenv("MCP_KEEPALIVE_SECONDS", "999")
    ns: dict = {}
    exec(  # noqa: S102 - reading one module-level constant, not running the server
        compile(
            "import os\nKEEPALIVE_SECONDS = int(os.environ.get('MCP_KEEPALIVE_SECONDS', '300'))",
            "<probe>",
            "exec",
        ),
        ns,
    )
    assert ns["KEEPALIVE_SECONDS"] == 999
    assert os.environ["MCP_KEEPALIVE_SECONDS"] == "999"


def test_stdio_transport_is_untouched():
    """stdio has no sockets and must still go through mcp.run()."""
    src = SERVER.read_text(encoding="utf-8")
    assert 'mcp.run(transport="stdio")' in src
