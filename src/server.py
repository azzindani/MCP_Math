"""MCP entry point — thin wrappers only. No domain logic here."""

from __future__ import annotations

import argparse
import logging
import os

import fastmcp
from starlette.requests import Request
from starlette.responses import JSONResponse

import engine
from shared import build_token_verifier

logging.basicConfig(level=logging.WARNING, stream=__import__("sys").stderr)

_VERSION = "0.1.0"  # keep in sync with pyproject.toml [project].version

mcp = fastmcp.FastMCP("math-mcp-server", auth=build_token_verifier("MATH"))


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Liveness check. Unauthenticated."""
    return JSONResponse({"status": "ok", "version": _VERSION})


@mcp.custom_route("/version", methods=["GET"])
async def version(request: Request) -> JSONResponse:
    """Report running version. Unauthenticated."""
    return JSONResponse({"current": _VERSION})


_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


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
    parser.add_argument("--host", default=os.environ.get("MATH_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MATH_PORT", "8765")))
    args = parser.parse_args()

    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
