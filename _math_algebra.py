"""Algebra sub-module: solve(), simplify(), diff(), integrate()."""

from __future__ import annotations

import sympy

from _math_helpers import (
    Eq,
    Symbol,
    UnsafeExpressionError,
    _error,
    build_response,
    fail,
    info,
    ok,
    sympify,
    sympy_diff,
    sympy_integrate,
    sympy_simplify,
    sympy_solve,
    validate_ast,
)


def _parse(expression: str, op: str, progress: list[dict]) -> tuple[sympy.Basic | None, dict | None]:
    """Parse an expression string; return (expr, None) or (None, error_dict)."""
    try:
        expr = sympify(expression)
        return expr, None
    except Exception as exc:
        progress.append(fail(f"Parse error: {exc}"))
        return None, _error(op, f"Parse error: {exc}", "Check expression syntax. Use ** for powers.", progress)


def solve(equation: str, variable: str = "x") -> dict:
    """Solve equation for variable. Returns list of solutions."""
    op = "solve"
    progress: list[dict] = []

    if not equation:
        return _error(op, "Empty equation.", "Provide an equation string, e.g. 'x**2 - 4'.")

    progress.append(info(f"Solving {equation!r} for {variable!r}"))

    # Parse the equation
    try:
        var = Symbol(variable)
        # Support both "lhs = rhs" and standalone expressions (= 0 implied)
        if "=" in equation:
            parts = equation.split("=", 1)
            lhs = sympify(parts[0].strip())
            rhs = sympify(parts[1].strip())
            expr = Eq(lhs, rhs)
        else:
            expr = sympify(equation)
    except Exception as exc:
        progress.append(fail(f"Parse error: {exc}"))
        return _error(
            op,
            f"Parse error: {exc}",
            "Use standard math notation, e.g. 'x**2 - 4 = 0' or 'x**2 - 4'.",
            progress,
        )

    progress.append(ok("Parsed"))

    try:
        validate_ast(expr)
    except UnsafeExpressionError as exc:
        return _error(op, f"Unsafe expression: {exc}", "Use standard algebraic expressions.", progress)

    try:
        solutions = sympy_solve(expr, var)
    except Exception as exc:
        progress.append(fail(f"Solve error: {exc}"))
        return _error(op, f"Could not solve: {exc}", "Try simplify() first, or check variable name.", progress)

    progress.append(ok(f"Found {len(solutions)} solution(s)"))

    serialized = [str(s) for s in solutions]
    return build_response(op, serialized, progress, extra={"variable": variable, "equation": equation})


def simplify(expression: str) -> dict:
    """Simplify algebraic expression. Returns simplified form."""
    op = "simplify"
    progress: list[dict] = []

    if not expression:
        return _error(op, "Empty expression.", "Provide an algebraic expression to simplify.")

    progress.append(info(f"Simplifying {expression!r}"))

    expr, err = _parse(expression, op, progress)
    if err:
        return err

    try:
        validate_ast(expr)
    except UnsafeExpressionError as exc:
        return _error(op, f"Unsafe expression: {exc}", "Use standard algebraic expressions.", progress)

    try:
        result = sympy_simplify(expr)
    except Exception as exc:
        progress.append(fail(f"Simplify error: {exc}"))
        return _error(op, f"Simplification failed: {exc}", "Check expression syntax.", progress)

    progress.append(ok(f"Simplified: {result}"))
    return build_response(op, str(result), progress, extra={"original": expression})


def diff(expression: str, variable: str = "x", order: int = 1) -> dict:
    """Differentiate expression. Returns derivative."""
    op = "diff"
    progress: list[dict] = []

    if not expression:
        return _error(op, "Empty expression.", "Provide an expression to differentiate.")

    if order < 1:
        return _error(op, "Order must be >= 1.", "Use order=1 for first derivative, order=2 for second, etc.")

    progress.append(info(f"Differentiating {expression!r} w.r.t. {variable!r} (order={order})"))

    expr, err = _parse(expression, op, progress)
    if err:
        return err

    try:
        validate_ast(expr)
    except UnsafeExpressionError as exc:
        return _error(op, f"Unsafe expression: {exc}", "Use standard algebraic expressions.", progress)

    try:
        var = Symbol(variable)
        result = sympy_diff(expr, var, order)
    except Exception as exc:
        progress.append(fail(f"Diff error: {exc}"))
        return _error(op, f"Differentiation failed: {exc}", "Check variable name and expression syntax.", progress)

    progress.append(ok(f"Derivative: {result}"))
    return build_response(
        op,
        str(result),
        progress,
        extra={"variable": variable, "order": order, "expression": expression},
    )


def integrate(expression: str, variable: str = "x", lower: str = "", upper: str = "") -> dict:
    """Integrate expression. Returns indefinite or definite integral."""
    op = "integrate"
    progress: list[dict] = []

    if not expression:
        return _error(op, "Empty expression.", "Provide an expression to integrate.")

    is_definite = bool(lower and upper)
    progress.append(
        info(f"Integrating {expression!r} w.r.t. {variable!r}" + (f" from {lower} to {upper}" if is_definite else ""))
    )

    expr, err = _parse(expression, op, progress)
    if err:
        return err

    try:
        validate_ast(expr)
    except UnsafeExpressionError as exc:
        return _error(op, f"Unsafe expression: {exc}", "Use standard algebraic expressions.", progress)

    try:
        var = Symbol(variable)
        if is_definite:
            lo = sympify(lower)
            hi = sympify(upper)
            result = sympy_integrate(expr, (var, lo, hi))
        else:
            result = sympy_integrate(expr, var)
    except Exception as exc:
        progress.append(fail(f"Integrate error: {exc}"))
        return _error(
            op,
            f"Integration failed: {exc}",
            "Check expression syntax. Use lower/upper for definite integrals.",
            progress,
        )

    progress.append(ok(f"Result: {result}"))
    extra: dict = {"variable": variable, "expression": expression}
    if is_definite:
        extra["lower"] = lower
        extra["upper"] = upper
        extra["type"] = "definite"
    else:
        extra["type"] = "indefinite"

    return build_response(op, str(result), progress, extra=extra)


__all__ = ["solve", "simplify", "diff", "integrate"]
