"""Shared imports, constants, and error helper for math sub-modules."""

from __future__ import annotations

# --- third-party imports (available after uv sync) ---
import numpy as np  # noqa: F401
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

try:
    from latex2sympy2 import latex2sympy  # noqa: F401

    HAS_LATEX2SYMPY2 = True
except ImportError:
    HAS_LATEX2SYMPY2 = False

import pint  # noqa: F401

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
    "parse_latex",
    "HAS_LATEX2SYMPY2",
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
