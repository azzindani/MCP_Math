"""Structured JSON response builder for MCP tool results."""

from __future__ import annotations

import math

import sympy


def build_response(
    op: str,
    # `dict` belongs here: describe() returns its statistics as one, and
    # _serialize has always walked dicts. The annotation just did not say so.
    result: sympy.Basic | str | float | list | dict | None,
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
    """Recursively convert SymPy objects to JSON-safe types.

    "JSON-safe" includes being a number JSON can write. `float("nan")` and
    `float("inf")` are neither: json.dumps emits the bare tokens NaN and
    Infinity, which no conformant parser accepts, and which several clients
    read back as a number regardless. A statistic that is undefined -- the
    skewness of five identical values, say -- arrives here as NaN and must not
    leave as one.
    """
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
        except TypeError, ValueError, AttributeError, OverflowError:
            return str(value)
        if not math.isfinite(f):
            # oo, -oo and nan are real SymPy answers; the symbol carries them.
            return str(value)
        # Return int if it's a whole number. The magnitude check comes first:
        # int() of an out-of-range float raises, and OverflowError was not in
        # the list above until calculate("oo") escaped through it.
        if abs(f) < 1e15 and f == int(f):
            return int(f)
        return f
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (int, float, str)):
        return value
    return str(value)
