"""Structured JSON response builder for MCP tool results."""

from __future__ import annotations

import sympy


def build_response(
    op: str,
    result: sympy.Basic | str | float | list | None,
    progress: list[dict],
    extra: dict | None = None,
) -> dict:
    """Convert raw SymPy result + metadata into a standard response dict.

    Args:
        op: Operation name (e.g. 'calculate', 'solve').
        result: Computed value — converted to str or float before JSON encoding.
        progress: List of progress log entries from shared.progress helpers.
        extra: Optional additional fields to merge into the response.

    Returns:
        Standard response dict with success, op, result, progress, token_estimate.
    """
    serialized = _serialize(result)

    response: dict = {
        "success": True,
        "op": op,
        "result": serialized,
        "progress": progress,
    }

    if extra:
        response.update(extra)

    response["token_estimate"] = len(str(response)) // 4
    return response


def build_error(op: str, error: str, hint: str, progress: list[dict] | None = None) -> dict:
    """Build a standard error response dict.

    Args:
        op: Operation name.
        error: Human-readable error description.
        hint: Actionable recovery instruction.
        progress: Optional progress entries collected before the error.

    Returns:
        Standard error dict with success=False.
    """
    response: dict = {
        "success": False,
        "op": op,
        "error": error,
        "hint": hint,
        "progress": progress or [],
    }
    response["token_estimate"] = len(str(response)) // 4
    return response


def _serialize(value: object) -> object:
    """Recursively convert SymPy objects to JSON-safe types."""
    if value is None:
        return None
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, sympy.Basic):
        # Try to get a float for numeric results
        try:
            f = float(value)
            # Return int if it's a whole number
            if f == int(f) and abs(f) < 1e15:
                return int(f)
            return f
        except (TypeError, ValueError, AttributeError):
            return str(value)
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(value)
