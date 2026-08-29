"""MCP entry point — thin wrappers only. No domain logic here."""

from __future__ import annotations

import argparse
import logging
import os

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

import engine
from shared import build_auth, build_oauth_bridge

logging.basicConfig(level=logging.WARNING, stream=__import__("sys").stderr)

_VERSION = "0.1.1"  # keep in sync with pyproject.toml [project].version

_HOST = os.environ.get("MATH_HOST", "127.0.0.1")
_PORT = int(os.environ.get("MATH_PORT", "8765"))
_oauth_bridge = build_oauth_bridge("MATH")
_token_verifier, _auth_settings = build_auth("MATH", _HOST, _PORT, _oauth_bridge)

mcp = FastMCP(
    "math-mcp-server",
    host=_HOST,
    port=_PORT,
    token_verifier=_token_verifier,
    auth=_auth_settings,
)
if _oauth_bridge is not None:
    _oauth_bridge.register_routes(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Liveness check. Unauthenticated."""
    return JSONResponse({"status": "ok", "version": _VERSION})


@mcp.custom_route("/version", methods=["GET"])
async def version(request: Request) -> JSONResponse:
    """Report running version. Unauthenticated."""
    return JSONResponse({"current": _VERSION})


# The official SDK types this properly; fastmcp 2.x accepted a bare dict, which
# is how eight tools shipped an annotation object nothing could validate.
_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


@mcp.tool(annotations=_ANNOTATIONS)
def calculate(expression: str) -> dict:
    """Evaluate arithmetic expression. Returns numeric result and steps."""
    return engine.calculate(expression)


@mcp.tool(annotations=_ANNOTATIONS)
def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """Convert value between units. Returns converted result."""
    return engine.convert_units(value, from_unit, to_unit)


@mcp.tool(annotations=_ANNOTATIONS)
def solve(equation: str, variable: str = "x") -> dict:
    """Solve equation for variable. Returns list of solutions."""
    return engine.solve(equation, variable)


@mcp.tool(annotations=_ANNOTATIONS)
def simplify(expression: str) -> dict:
    """Simplify algebraic expression. Returns simplified form."""
    return engine.simplify(expression)


@mcp.tool(annotations=_ANNOTATIONS)
def diff(expression: str, variable: str = "x", order: int = 1) -> dict:
    """Differentiate expression. Returns derivative."""
    return engine.diff(expression, variable, order)


@mcp.tool(annotations=_ANNOTATIONS)
def integrate(expression: str, variable: str = "x", lower: str = "", upper: str = "") -> dict:
    """Integrate expression. Returns indefinite or definite integral."""
    return engine.integrate(expression, variable, lower, upper)


@mcp.tool(annotations=_ANNOTATIONS)
def describe(dataset: list[float]) -> dict:
    """Compute descriptive statistics for a dataset. Returns summary."""
    return engine.describe(dataset)


@mcp.tool(annotations=_ANNOTATIONS)
def eval_latex(formula: str, variables: dict[str, float] | None = None) -> dict:
    """Evaluate LaTeX formula with variable substitution. Returns result."""
    return engine.eval_latex(formula, variables)


def main() -> None:
    parser = argparse.ArgumentParser(description="Math MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=os.environ.get("MATH_TRANSPORT", "stdio"))
    args = parser.parse_args()

    # Host and port are settings on the server object in the official SDK, not
    # arguments to run(), so they are bound above where FastMCP is built. The
    # transport is spelled "streamable-http" there; "http" is fastmcp 2.x's
    # name for it and is silently not a valid choice.
    if args.transport == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
