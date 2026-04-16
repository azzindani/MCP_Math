"""Engine package: thin router + sandbox, deps, formatter."""

# Internal engine utilities
# Tool functions re-exported for tests and server.py
from _math_algebra import diff, integrate, simplify, solve
from _math_arithmetic import calculate, convert_units
from _math_latex import eval_latex
from _math_statistics import describe, regression

from .deps import build_dag, topological_sort
from .formatter import build_error, build_response
from .sandbox import UnsafeExpressionError, evaluate_with_timeout, validate_ast

__all__ = [
    # utilities
    "build_dag",
    "topological_sort",
    "build_error",
    "build_response",
    "UnsafeExpressionError",
    "evaluate_with_timeout",
    "validate_ast",
    # tools
    "calculate",
    "convert_units",
    "solve",
    "simplify",
    "diff",
    "integrate",
    "describe",
    "regression",
    "eval_latex",
]
