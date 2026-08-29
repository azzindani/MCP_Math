"""Shared imports, constants, and error helper for math sub-modules."""

from __future__ import annotations

# --- third-party imports (available after uv sync) ---
import numpy as np  # noqa: F401
import pint  # noqa: F401
import sympy  # noqa: F401
from scipy import stats as scipy_stats  # noqa: F401
from sympy import (  # noqa: F401
    Eq,
    Symbol,
    sympify,
)
from sympy import (
    diff as sympy_diff,
)
from sympy import (
    integrate as sympy_integrate,
)
from sympy import (
    simplify as sympy_simplify,
)
from sympy import (
    solve as sympy_solve,
)
from sympy.parsing.latex import parse_latex  # noqa: F401
from sympy.parsing.sympy_parser import (
    convert_xor,
    function_exponentiation,
    implicit_application,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)

from engine.formatter import build_error, build_response  # noqa: F401

# --- engine imports ---
from engine.sandbox import UnsafeExpressionError, evaluate_with_timeout, validate_ast  # noqa: F401

# --- shared imports ---
from shared.platform_utils import get_max_dataset_size, is_constrained_mode  # noqa: F401
from shared.progress import fail, info, ok, warn  # noqa: F401

# --- constants ---
ALLOWED_SYMPY_NODES: frozenset[str] = frozenset(
    {
        "Add",
        "Mul",
        "Pow",
        "Number",
        "Integer",
        "Float",
        "Rational",
        "Symbol",
        "Dummy",
        "One",
        "Zero",
        "NegativeOne",
        "Half",
        "Pi",
        "Exp1",
        "ImaginaryUnit",
        "Infinity",
        "NegativeInfinity",
        "ComplexInfinity",
        "NaN",
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "atan2",
        "sinh",
        "cosh",
        "tanh",
        "exp",
        "log",
        "sqrt",
        "Abs",
        "sign",
        "ceiling",
        "floor",
        "factorial",
        "gamma",
        "Eq",
        "Ne",
        "Lt",
        "Le",
        "Gt",
        "Ge",
        "And",
        "Or",
        "Not",
    }
)


# Plain sympify()/parse_expr() run the input string through Python's eval()
# during PARSING itself — before validate_ast() ever sees the result. That
# means '__import__("os").system(...)' and dunder chains like
# '().__class__.__base__.__subclasses__()' execute (or walk live class
# objects) as a side effect of parsing, which no post-hoc AST check can
# undo. _SAFE_SYMPY_GLOBALS strips __builtins__ so bare dangerous names
# fall back to being treated as sympy symbols/functions instead of real
# Python callables, and rejecting '__' closes the dunder-attribute escape
# route that doesn't need builtins at all.
_SAFE_SYMPY_GLOBALS: dict = {k: v for k, v in vars(sympy).items() if not k.startswith("_")}
_SAFE_SYMPY_GLOBALS["__builtins__"] = {}


# Humans and LLMs write powers as x^2 and products as 2x -- the README's own
# usage examples do. standard_transformations alone reads '^' as bitwise XOR,
# so 'x^2' became Symbol ^ Integer and surfaced a raw Python TypeError, while
# eval_latex (which parses LaTeX) read the same string as a power.
# One server must not give one string two meanings.
#
# This is implicit_multiplication_application MINUS split_symbols, and the
# omission is the point: split_symbols shatters any multi-letter name, turning
# 'velocity^2 - 4' into 'c*e*i*l*o*t*v*y**2 - 4' and returning a confident
# wrong answer instead of an error. Silent corruption is worse than the bug
# being fixed, so the bundle is unpacked and that one member left out.
_TRANSFORMS = standard_transformations + (
    convert_xor,
    implicit_multiplication,
    implicit_application,
    function_exponentiation,
)


def safe_sympify(expression: str, evaluate: bool = True):
    """Parse a math expression string without exposing eval() to builtins."""
    if "__" in expression:
        raise ValueError("expression must not contain '__'")
    return parse_expr(
        expression,
        global_dict=_SAFE_SYMPY_GLOBALS,
        transformations=_TRANSFORMS,
        evaluate=evaluate,
    )


def _error(op: str, msg: str, hint: str, progress: list[dict] | None = None) -> dict:
    """Return a standard error dict. Shorthand for build_error()."""
    return build_error(op, msg, hint, progress)


__all__ = [
    "np",
    "sympy",
    "scipy_stats",
    "Eq",
    "Symbol",
    "sympy_diff",
    "sympy_integrate",
    "sympy_simplify",
    "sympy_solve",
    "sympify",
    "safe_sympify",
    "parse_latex",
    "pint",
    "UnsafeExpressionError",
    "evaluate_with_timeout",
    "validate_ast",
    "build_error",
    "build_response",
    "get_max_dataset_size",
    "is_constrained_mode",
    "fail",
    "info",
    "ok",
    "warn",
    "ALLOWED_SYMPY_NODES",
    "_error",
]
