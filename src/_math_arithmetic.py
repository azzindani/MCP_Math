"""Arithmetic sub-module: calculate() and convert_units()."""

from __future__ import annotations

from _math_helpers import (
    UnsafeExpressionError,
    _error,
    build_response,
    evaluate_with_timeout,
    fail,
    info,
    ok,
    pint,
    sympify,
    validate_ast,
)

_ureg = pint.UnitRegistry()


def calculate(expression: str) -> dict:
    """Evaluate arithmetic expression. Returns numeric result and steps."""
    op = "calculate"
    progress: list[dict] = []

    if not expression or not expression.strip():
        return _error(op, "Empty expression.", "Provide a numeric expression, e.g. '2 + 2 * 3'.")

    progress.append(info(f"Parsing: {expression!r}"))

    try:
        expr = sympify(expression, evaluate=False)
    except Exception as exc:
        return _error(
            op,
            f"Parse error: {exc}",
            "Check syntax. Use ** for powers, sqrt() for roots.",
            progress,
        )

    progress.append(ok("Parsed successfully"))

    try:
        validate_ast(expr)
    except UnsafeExpressionError as exc:
        progress.append(fail(f"AST blocked: {exc}"))
        return _error(
            op,
            f"Unsafe expression: {exc}",
            "calculate() handles numeric expressions only. Use solve() for equations.",
            progress,
        )

    progress.append(ok("AST validated"))

    try:
        result = evaluate_with_timeout(expr, timeout=5, precision=15)
    except TimeoutError:
        progress.append(fail("Timeout"))
        return _error(op, "Evaluation timed out.", "Simplify the expression or split into smaller parts.", progress)
    except Exception as exc:
        progress.append(fail(f"Eval error: {exc}"))
        return _error(op, f"Evaluation error: {exc}", "Check for division by zero or invalid operations.", progress)

    progress.append(ok(f"Result: {result}"))

    # Serialize
    try:
        numeric = float(result)
        if numeric == int(numeric) and abs(numeric) < 1e15:
            numeric_out: int | float = int(numeric)
        else:
            numeric_out = numeric
    except (TypeError, ValueError):
        numeric_out = str(result)  # type: ignore[assignment]

    return build_response(
        op,
        numeric_out,
        progress,
        extra={
            "expression_parsed": str(expr),
            "steps": [p["message"] for p in progress],
        },
    )


def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """Convert value between units. Returns converted result."""
    op = "convert_units"
    progress: list[dict] = []

    if not from_unit or not to_unit:
        return _error(op, "Missing unit name.", "Provide both from_unit and to_unit strings.")

    progress.append(info(f"Converting {value} {from_unit!r} → {to_unit!r}"))

    try:
        qty = _ureg.Quantity(value, from_unit)
    except Exception as exc:
        progress.append(fail(f"Unknown from_unit: {exc}"))
        return _error(
            op,
            f"Unknown unit '{from_unit}': {exc}",
            "Check unit names at pint.readthedocs.io/en/stable/user/units.html",
            progress,
        )

    try:
        converted = qty.to(to_unit)
    except pint.DimensionalityError as exc:
        progress.append(fail(f"Incompatible units: {exc}"))
        return _error(
            op,
            f"Cannot convert '{from_unit}' to '{to_unit}': {exc}",
            "Ensure both units measure the same physical quantity (e.g. both length).",
            progress,
        )
    except Exception as exc:
        progress.append(fail(f"Conversion error: {exc}"))
        return _error(
            op,
            f"Conversion failed: {exc}",
            "Check unit names at pint.readthedocs.io/en/stable/user/units.html",
            progress,
        )

    result_val = float(converted.magnitude)
    if result_val == int(result_val) and abs(result_val) < 1e15:
        result_out: int | float = int(result_val)
    else:
        result_out = result_val

    progress.append(ok(f"Result: {result_out} {to_unit}"))

    return build_response(
        op,
        result_out,
        progress,
        extra={
            "from": f"{value} {from_unit}",
            "to": f"{result_out} {to_unit}",
        },
    )


__all__ = ["calculate", "convert_units"]
