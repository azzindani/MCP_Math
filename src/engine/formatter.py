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


def classify_number(value: object) -> tuple[str, str]:
    """Say what kind of answer a computed result is, and why.

    `_serialize` below turns a non-finite result into its symbol, because JSON
    has no token for infinity or NaN. That settled how to *write* the value and
    left the caller with no way to tell "the answer is 7" from "there is no
    answer": calculate("1/0") returned success=true with result "zoo", and the
    contract (§7) says success is the first key the model checks. describe()
    had the same problem and reports `null` plus an `undefined` block naming the
    reason; this is that signal for the tools that return a single value.

    Returns (kind, reason) where kind is one of:
        "real"      finite real number — safe to report as a value
        "symbolic"  still has free symbols; not a number, and not meant to be
        "undefined" nan or zoo — the expression has no value
        "infinite"  +/-oo — a real limit, but not a number
        "complex"   finite, but not on the real line
    """
    if not isinstance(value, sympy.Basic):
        return ("real", "")
    if not value.is_number:
        return ("symbolic", "")
    # sympy collapses these into their singletons (nan + 1 is nan), but an
    # unevaluated tree can still carry one, so identity is checked with `has`.
    if value.has(sympy.nan):
        return ("undefined", "the expression is indeterminate (0/0 or equivalent)")
    if value.has(sympy.zoo):
        return ("undefined", "the expression divides by zero")
    if value.is_finite is False:
        return ("infinite", "the expression grows without bound")
    if value.is_real is False:
        return ("complex", "the result is not on the real line")
    return ("real", "")


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
