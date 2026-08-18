"""LaTeX sub-module: eval_latex() — 6-stage internal pipeline."""

from __future__ import annotations

import re as _re

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
    safe_sympify,
    validate_ast,
)

if HAS_LATEX2SYMPY2:
    from latex2sympy2 import latex2sympy
else:
    from sympy.parsing.latex import parse_latex as latex2sympy  # type: ignore[assignment]

from engine.deps import build_dag, topological_sort

# Multi-letter names in a formula: "spends", "click_rate". Single letters are
# excluded because latex2sympy handles those as ordinary symbols, and LaTeX
# command names are excluded because they are markup, not variables.
_WORD = _re.compile(r"(?<!\\)\b[A-Za-z_][A-Za-z0-9_]{1,}\b")
_LATEX_COMMANDS = frozenset(
    {
        "frac",
        "sqrt",
        "sum",
        "prod",
        "int",
        "lim",
        "log",
        "ln",
        "exp",
        "sin",
        "cos",
        "tan",
        "cdot",
        "times",
        "div",
        "left",
        "right",
        "pi",
        "theta",
        "alpha",
        "beta",
        "gamma",
        "infty",
        "text",
        "mathrm",
        "operatorname",
    }
)


def _parse_latex(formula: str):
    """Parse LaTeX, leaving the parser exactly as it was found.

    latex2sympy2 keeps its symbol tables in module globals and rebinds one of
    them -- `var` -- to a bare Symbol partway through a failing parse. Every
    later call then does a membership test against that Symbol, which is where
    "argument of type 'Symbol' is not iterable" actually comes from. So a single
    malformed formula disabled eval_latex for the lifetime of the process: on a
    long-running server every subsequent call failed, with an error describing
    neither the caller's formula nor the real problem.

    The library cannot be fixed from here, so its globals are snapshotted and
    put back whether the parse succeeds or raises.
    """
    if not HAS_LATEX2SYMPY2:
        return latex2sympy(formula)

    import latex2sympy2 as _l2s

    saved = {name: getattr(_l2s, name, None) for name in ("var", "variances", "VARIABLE_VALUES")}
    try:
        return latex2sympy(formula)
    finally:
        for name, value in saved.items():
            if value is not None:
                setattr(_l2s, name, value)


def _bind_names(formula: str, variables: dict) -> tuple[str, list[str]]:
    """Replace multi-letter names in `formula` with their supplied values.

    Returns (formula, names_bound). Longest names are substituted first so that
    a shorter name is never matched inside a longer one -- binding "click"
    before "click_rate" would corrupt the formula.
    """
    if not variables:
        return formula, []

    bound: list[str] = []
    out = formula
    for name in sorted(variables, key=len, reverse=True):
        if len(name) < 2 or name in _LATEX_COMMANDS:
            continue
        # The negative lookbehind keeps \frac from being treated as the name
        # "frac", and the word boundaries keep "a" out of the middle of "alpha".
        pattern = _re.compile(rf"(?<!\\)\b{_re.escape(name)}\b")
        if pattern.search(out):
            out = pattern.sub(f"({variables[name]})", out)
            bound.append(name)
    return out, bound


def _parse_hint(formula: str, variables: dict, exc: Exception) -> str:
    """Explain what actually went wrong parsing a formula.

    The old hint said "Check LaTeX syntax" for every failure. For the most
    common one -- a valid formula written over named quantities, like
    \\frac{spends}{clicks}, with no variables map -- that is worse than no hint
    at all: the syntax is correct, so it sends the caller to inspect something
    that is not the problem. latex2sympy surfaces this as "argument of type
    'Symbol' is not iterable", which explains nothing to anyone.
    """
    names = {m.group(0) for m in _WORD.finditer(formula)} - _LATEX_COMMANDS
    unbound = sorted(names - set(variables))
    if unbound:
        listed = ", ".join(unbound)
        return (
            f"The formula uses named quantities with no value supplied: {listed}. "
            f"Pass them in variables, e.g. variables={{'{unbound[0]}': 1.0}}. "
            f"To differentiate or rearrange symbolically instead, use diff(), solve() or simplify()."
        )
    return "Check LaTeX syntax. Fractions: \\frac{a}{b}, powers: x^{2}."


def eval_latex(formula: str, variables: dict[str, float] | None = None) -> dict:
    """Evaluate LaTeX formula with variable substitution. Returns result."""
    op = "eval_latex"
    progress: list[dict] = []
    variables = variables or {}

    if not formula or not formula.strip():
        return _error(op, "Empty formula.", "Provide a LaTeX formula string, e.g. r'\\frac{a}{b}'.")

    # ── Stage 0: Bind named quantities ───────────────────────────────────────
    # latex2sympy cannot parse a multi-letter name at all -- \frac{spends}{clicks}
    # fails with "argument of type 'Symbol' is not iterable" whether or not
    # values were supplied, because it breaks in the parser, before anything
    # could be substituted. That made the documented use case for this tool
    # (a real formula plus a variables map) impossible. Binding the names in the
    # formula text first means the parser only ever sees numbers.
    formula_to_parse, bound = _bind_names(formula, variables)
    if bound:
        progress.append(info(f"Stage 0: Bound {', '.join(bound)}"))

    # ── Stage 1: Parse ────────────────────────────────────────────────────────
    progress.append(info("Stage 1: Parsing LaTeX"))
    try:
        expr = _parse_latex(formula_to_parse)
    except Exception as exc:
        progress.append(fail(f"LaTeX parse error: {exc}"))
        return _error(op, f"LaTeX parse error: {exc}", _parse_hint(formula, variables, exc), progress)
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
                    sub_expr = safe_sympify(val.format(**resolved))
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
