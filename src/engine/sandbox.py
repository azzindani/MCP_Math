"""AST whitelist validator and cross-platform timeout evaluator."""

import platform
import sys
import threading
from typing import Any

import sympy

# Allowed SymPy node types (safe math nodes only)
ALLOWED_SYMPY_TYPES = (
    sympy.Expr,
    sympy.Basic,
    sympy.core.numbers.Number,
    sympy.core.symbol.Symbol,
    sympy.core.symbol.Dummy,
    sympy.core.add.Add,
    sympy.core.mul.Mul,
    sympy.core.power.Pow,
    sympy.core.function.AppliedUndef,
    sympy.core.relational.Relational,
    sympy.logic.boolalg.BooleanAtom,
)

# Blocked SymPy function names (code execution risk)
BLOCKED_NAMES: set[str] = {"Lambda", "Piecewise", "Subs"}


class UnsafeExpressionError(ValueError):
    """Raised when expression contains non-math SymPy nodes."""


def validate_ast(expr: Any) -> None:
    """Walk SymPy expression tree; raise UnsafeExpressionError on unsafe nodes.

    Args:
        expr: A SymPy expression to validate.
    """
    if expr is None:
        return

    # Handle lists/tuples of expressions (e.g., solve() returns a list)
    if isinstance(expr, (list, tuple)):
        for item in expr:
            validate_ast(item)
        return

    # Check for blocked class names
    cls_name = type(expr).__name__
    if cls_name in BLOCKED_NAMES:
        raise UnsafeExpressionError(f"Blocked SymPy node type: {cls_name}")

    # All SymPy math nodes must be subclasses of Basic
    if not isinstance(expr, sympy.Basic):
        # Allow plain Python numbers that sympify produces
        if isinstance(expr, (int, float, complex)):
            return
        raise UnsafeExpressionError(f"Non-SymPy node in expression tree: {type(expr)}")

    # Recurse into arguments
    for arg in expr.args:
        validate_ast(arg)


def _evaluate_expr(expr: sympy.Expr, precision: int, result_holder: list, error_holder: list) -> None:
    """Worker function for threaded evaluation."""
    try:
        result_holder.append(expr.evalf(precision))
    except Exception as exc:  # noqa: BLE001
        error_holder.append(exc)


def evaluate_with_timeout(expr: sympy.Expr, timeout: int = 5, precision: int = 15) -> sympy.Expr:
    """Evaluate a SymPy expression with a cross-platform timeout.

    Uses signal.alarm on Unix and threading.Timer on Windows.

    Args:
        expr: Validated SymPy expression.
        timeout: Seconds before TimeoutError is raised.
        precision: Decimal digits for evalf().

    Returns:
        Evaluated SymPy Float or expression.
    """
    if platform.system() == "Windows" or sys.platform == "win32":
        return _evaluate_with_thread(expr, timeout, precision)
    else:
        return _evaluate_with_signal(expr, timeout, precision)


def _evaluate_with_signal(expr: sympy.Expr, timeout: int, precision: int) -> sympy.Expr:
    """Unix implementation using signal.alarm."""
    import signal

    def _handler(signum: int, frame: Any) -> None:  # noqa: ARG001
        raise TimeoutError(f"Evaluation timed out after {timeout}s")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout)
    try:
        result = expr.evalf(precision)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    return result


def _evaluate_with_thread(expr: sympy.Expr, timeout: int, precision: int) -> sympy.Expr:
    """Windows/cross-platform implementation using threading.Timer."""
    result_holder: list = []
    error_holder: list = []

    thread = threading.Thread(target=_evaluate_expr, args=(expr, precision, result_holder, error_holder))
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise TimeoutError(f"Evaluation timed out after {timeout}s")
    if error_holder:
        raise error_holder[0]
    if not result_holder:
        raise RuntimeError("Evaluation produced no result")
    return result_holder[0]
