"""LaTeX sub-module: eval_latex() — 6-stage internal pipeline."""

from __future__ import annotations

import re as _re

import sympy

from _math_helpers import (
    UnsafeExpressionError,
    _error,
    build_response,
    evaluate_with_timeout,
    fail,
    info,
    ok,
    parse_latex,
    safe_sympify,
    validate_ast,
)
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
    """Parse LaTeX into a SymPy expression.

    This used to snapshot and restore latex2sympy2's module globals: that
    library rebound one of them -- `var` -- to a bare Symbol partway through a
    failing parse, so one malformed formula disabled eval_latex for the lifetime
    of the process. latex2sympy2 pinned antlr4-python3-runtime==4.7.2, which
    imports `typing.io`, removed in Python 3.13; it has been unmaintained since
    2022, so the pin could not move and the package was dropped. SymPy's own
    parser keeps no state between calls, leaving nothing to restore.
    """
    return parse_latex(formula)


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
    unbound = _named_quantities(formula, variables)
    if unbound:
        return _unbound_hint(unbound)
    return "Check LaTeX syntax. Fractions: \\frac{a}{b}, powers: x^{2}."


def _named_quantities(formula: str, variables: dict) -> list[str]:
    """Multi-letter names written in the formula that have no supplied value."""
    names = {m.group(0) for m in _WORD.finditer(formula)} - _LATEX_COMMANDS
    return sorted(names - set(variables))


def _unbound_hint(unbound: list[str]) -> str:
    """Name the quantities that have no value, and how to supply them."""
    listed = ", ".join(unbound)
    return (
        f"The formula uses named quantities with no value supplied: {listed}. "
        f"Pass them in variables, e.g. variables={{'{unbound[0]}': 1.0}}. "
        f"To differentiate or rearrange symbolically instead, use diff(), solve() or simplify()."
    )


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

    # ── Stage 4b: Every name must have a value ────────────────────────────────
    # eval_latex returns a number; a symbol still standing here means the caller
    # left a quantity unbound. That used to surface on its own, because
    # latex2sympy2 could not parse a multi-letter name at all and crashed in the
    # parser. SymPy's parser accepts them, so \frac{spends}{clicks} now parses
    # cleanly and would evaluate to the string "spends/clicks" under a success
    # flag -- an answer shaped like a result that is not one. Ask the question
    # directly instead of inferring it from a parser's failure.
    leftover = sorted(str(s) for s in expr.free_symbols)
    if leftover:
        # SymPy's LaTeX parser reads a multi-letter name as a product of single
        # letters, so \frac{spends}{clicks} leaves symbols c, ds, e, i, k, l, n,
        # p, s -- none of which the caller wrote. Report the names as typed, and
        # fall back to the symbols only when the formula really does use single
        # letters, which _WORD deliberately does not match.
        unbound = _named_quantities(formula, variables) or leftover
        progress.append(fail(f"Unbound: {', '.join(unbound)}"))
        return _error(
            op,
            f"No value supplied for: {', '.join(unbound)}.",
            _unbound_hint(unbound),
            progress,
        )

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
