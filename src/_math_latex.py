"""LaTeX sub-module: eval_latex() — 6-stage internal pipeline."""

from __future__ import annotations

import sympy

from _math_helpers import (
    HAS_LATEX2SYMPY2,
    UnsafeExpressionError,
    _error,
    build_response,
    evaluate_with_timeout,
    fail,
    info,
    ok,
    sympify,
    validate_ast,
)

if HAS_LATEX2SYMPY2:
    from latex2sympy2 import latex2sympy
else:
    from sympy.parsing.latex import parse_latex as latex2sympy  # type: ignore[assignment]

from engine.deps import build_dag, topological_sort


def eval_latex(formula: str, variables: dict[str, float] | None = None) -> dict:
    """Evaluate LaTeX formula with variable substitution. Returns result."""
    op = "eval_latex"
    progress: list[dict] = []
    variables = variables or {}

    if not formula or not formula.strip():
        return _error(op, "Empty formula.", "Provide a LaTeX formula string, e.g. r'\\frac{a}{b}'.")

    # ── Stage 1: Parse ────────────────────────────────────────────────────────
    progress.append(info("Stage 1: Parsing LaTeX"))
    try:
        expr = latex2sympy(formula)
    except Exception as exc:
        progress.append(fail(f"LaTeX parse error: {exc}"))
        return _error(
            op,
            f"LaTeX parse error: {exc}",
            "Check LaTeX syntax. Fractions: \\frac{a}{b}, powers: x^{2}.",
            progress,
        )
    progress.append(ok("Parsed"))

    # ── Stage 2: Validate AST ─────────────────────────────────────────────────
    progress.append(info("Stage 2: Validating AST"))
    try:
        validate_ast(expr)
    except UnsafeExpressionError as exc:
        progress.append(fail(f"Unsafe: {exc}"))
        return _error(op, f"Unsafe expression: {exc}", "Only standard math operations are allowed.", progress)
    progress.append(ok("AST safe"))

    # ── Stage 3: Resolve dependencies (only when sub-formulas present) ────────
    str_vars = {k: v for k, v in variables.items() if isinstance(v, str)}
    float_vars = {k: float(v) for k, v in variables.items() if not isinstance(v, str)}  # type: ignore[arg-type]

    if str_vars:
        progress.append(info("Stage 3: Resolving sub-formula dependencies"))
        try:
            dag = build_dag(variables)  # type: ignore[arg-type]
            order = topological_sort(dag)
        except ValueError as exc:
            progress.append(fail(f"Dependency error: {exc}"))
            return _error(
                op,
                f"Variable dependency error: {exc}",
                "Check for circular references in your variables dict.",
                progress,
            )
        # Evaluate string sub-formulas in topological order
        resolved: dict[str, float] = dict(float_vars)
        for name in order:
            val = variables.get(name)
            if isinstance(val, str):
                try:
                    sub_expr = sympify(val.format(**resolved))
                    sub_result = evaluate_with_timeout(sub_expr, timeout=5, precision=15)
                    resolved[name] = float(sub_result)
                except Exception as exc:
                    progress.append(fail(f"Sub-formula '{name}' error: {exc}"))
                    return _error(
                        op,
                        f"Error evaluating sub-formula '{name}': {exc}",
                        "Ensure sub-formulas are valid SymPy expressions.",
                        progress,
                    )
        float_vars = resolved
        progress.append(ok("Sub-formulas resolved"))
    else:
        progress.append(info("Stage 3: No sub-formulas — skipped"))

    # ── Stage 4: Substitute ───────────────────────────────────────────────────
    progress.append(info("Stage 4: Substituting variables"))
    if float_vars:
        subs_map = {sympy.Symbol(k): v for k, v in float_vars.items()}
        try:
            expr = expr.subs(subs_map)
        except Exception as exc:
            progress.append(fail(f"Substitution error: {exc}"))
            return _error(op, f"Substitution failed: {exc}", "Check variable names match symbols in formula.", progress)
        progress.append(ok(f"Substituted {len(float_vars)} variable(s)"))
    else:
        progress.append(info("No variables to substitute"))

    # ── Stage 5: Evaluate ─────────────────────────────────────────────────────
    progress.append(info("Stage 5: Evaluating"))
    try:
        result = evaluate_with_timeout(expr, timeout=5, precision=15)
    except TimeoutError:
        progress.append(fail("Timeout"))
        return _error(op, "Evaluation timed out.", "Simplify the formula or break it into smaller parts.", progress)
    except Exception as exc:
        progress.append(fail(f"Eval error: {exc}"))
        return _error(
            op,
            f"Evaluation error: {exc}",
            "Ensure all variables are provided or the expression is fully numeric.",
            progress,
        )
    progress.append(ok(f"Result: {result}"))

    # ── Stage 6: Format ───────────────────────────────────────────────────────
    progress.append(info("Stage 6: Formatting output"))
    try:
        numeric = float(result)
        if numeric == int(numeric) and abs(numeric) < 1e15:
            result_out: int | float = int(numeric)
        else:
            result_out = numeric
    except (TypeError, ValueError):
        result_out = str(result)  # type: ignore[assignment]

    return build_response(
        op,
        result_out,
        progress,
        extra={
            "formula_parsed": str(expr),
            "substitutions": {k: v for k, v in float_vars.items()},
            "steps": [p["message"] for p in progress],
        },
    )


__all__ = ["eval_latex"]
