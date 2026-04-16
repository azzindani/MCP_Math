"""Comprehensive tests for all 8 math MCP tools via engine.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import engine

FIXTURES = Path(__file__).parent / "fixtures"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def assert_success(result: dict, op: str) -> None:
    assert result["success"] is True, f"Expected success, got: {result}"
    assert result["op"] == op
    assert "token_estimate" in result
    assert result["token_estimate"] > 0
    assert "progress" in result


def assert_failure(result: dict, op: str) -> None:
    assert result["success"] is False, f"Expected failure, got: {result}"
    assert result["op"] == op
    assert "error" in result
    assert "hint" in result
    assert result["hint"] not in ("Invalid input.", "Try again.")
    assert "token_estimate" in result


# ─────────────────────────────────────────────────────────────────────────────
# shared/ tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformUtils:
    def test_default_mode(self, monkeypatch):
        monkeypatch.delenv("MCP_CONSTRAINED_MODE", raising=False)
        from shared.platform_utils import get_max_dataset_size, get_max_results, is_constrained_mode
        assert is_constrained_mode() is False
        assert get_max_results() == 50
        assert get_max_dataset_size() == 10_000

    def test_constrained_mode(self, monkeypatch):
        monkeypatch.setenv("MCP_CONSTRAINED_MODE", "1")
        # Re-import to pick up new env
        import importlib

        import shared.platform_utils as pu
        importlib.reload(pu)
        assert pu.is_constrained_mode() is True
        assert pu.get_max_results() == 10
        assert pu.get_max_dataset_size() == 100
        # Restore
        importlib.reload(pu)

    def test_env_zero(self, monkeypatch):
        monkeypatch.setenv("MCP_CONSTRAINED_MODE", "0")
        import importlib

        import shared.platform_utils as pu
        importlib.reload(pu)
        assert pu.is_constrained_mode() is False


class TestProgress:
    def test_ok(self):
        from shared.progress import ok
        r = ok("done")
        assert r == {"level": "ok", "message": "done"}

    def test_fail(self):
        from shared.progress import fail
        r = fail("oops")
        assert r == {"level": "fail", "message": "oops"}

    def test_info(self):
        from shared.progress import info
        r = info("starting")
        assert r == {"level": "info", "message": "starting"}

    def test_warn(self):
        from shared.progress import warn
        r = warn("careful")
        assert r == {"level": "warn", "message": "careful"}


# ─────────────────────────────────────────────────────────────────────────────
# engine/sandbox.py tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSandbox:
    def test_validate_safe_expression(self):
        import sympy

        from engine.sandbox import validate_ast
        expr = sympy.sympify("x**2 + 2*x + 1")
        validate_ast(expr)  # must not raise

    def test_validate_list_of_expressions(self):
        import sympy

        from engine.sandbox import validate_ast
        exprs = [sympy.Integer(1), sympy.Symbol("x")]
        validate_ast(exprs)  # must not raise

    def test_evaluate_with_timeout_basic(self):
        import sympy

        from engine.sandbox import evaluate_with_timeout
        expr = sympy.sympify("2 + 2")
        result = evaluate_with_timeout(expr, timeout=5)
        assert float(result) == 4.0

    def test_evaluate_with_timeout_trig(self):
        import sympy

        from engine.sandbox import evaluate_with_timeout
        expr = sympy.sin(sympy.pi / 2)
        result = evaluate_with_timeout(expr, timeout=5)
        assert abs(float(result) - 1.0) < 1e-10

    def test_validate_blocks_lambda(self):
        import sympy

        from engine.sandbox import UnsafeExpressionError, validate_ast
        expr = sympy.Lambda(sympy.Symbol("x"), sympy.Symbol("x") ** 2)
        with pytest.raises(UnsafeExpressionError, match="Lambda"):
            validate_ast(expr)

    def test_validate_blocks_piecewise(self):
        import sympy

        from engine.sandbox import UnsafeExpressionError, validate_ast
        expr = sympy.Piecewise((1, sympy.Symbol("x") > 0), (0, True))
        with pytest.raises(UnsafeExpressionError, match="Piecewise"):
            validate_ast(expr)


# ─────────────────────────────────────────────────────────────────────────────
# engine/deps.py tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDeps:
    def test_build_dag_float_only(self):
        from engine.deps import build_dag
        dag = build_dag({"a": 1.0, "b": 2.0})
        assert dag == {"a": set(), "b": set()}

    def test_build_dag_with_string_dep(self):
        from engine.deps import build_dag
        dag = build_dag({"a": 1.0, "b": "a + 1"})
        assert "a" in dag["b"]

    def test_topological_sort_simple(self):
        from engine.deps import topological_sort
        dag = {"a": set(), "b": {"a"}}
        order = topological_sort(dag)
        assert order.index("a") < order.index("b")

    def test_topological_sort_cycle(self):
        from engine.deps import topological_sort
        dag = {"a": {"b"}, "b": {"a"}}
        with pytest.raises(ValueError, match="Circular dependency"):
            topological_sort(dag)


# ─────────────────────────────────────────────────────────────────────────────
# engine/formatter.py tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatter:
    def test_build_response_basic(self):
        from engine.formatter import build_response
        r = build_response("calculate", 42, [])
        assert r["success"] is True
        assert r["result"] == 42
        assert r["token_estimate"] > 0

    def test_build_error_basic(self):
        from engine.formatter import build_error
        r = build_error("calculate", "bad input", "fix it")
        assert r["success"] is False
        assert r["error"] == "bad input"
        assert r["hint"] == "fix it"

    def test_serialize_sympy(self):
        import sympy

        from engine.formatter import build_response
        r = build_response("test", sympy.Integer(7), [])
        assert r["result"] == 7

    def test_serialize_sympy_float(self):
        import sympy

        from engine.formatter import build_response
        r = build_response("test", sympy.Float("3.14"), [])
        assert abs(r["result"] - 3.14) < 0.001


# ─────────────────────────────────────────────────────────────────────────────
# calculate() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculate:
    def test_happy_path_addition(self):
        r = engine.calculate("2 + 3")
        assert_success(r, "calculate")
        assert r["result"] == 5

    def test_happy_path_power(self):
        r = engine.calculate("2 ** 10")
        assert_success(r, "calculate")
        assert r["result"] == 1024

    def test_happy_path_sqrt(self):
        r = engine.calculate("sqrt(16)")
        assert_success(r, "calculate")
        assert r["result"] == 4

    def test_division(self):
        r = engine.calculate("10 / 4")
        assert_success(r, "calculate")
        assert abs(r["result"] - 2.5) < 1e-10

    def test_fixtures(self):
        fixtures = json.loads((FIXTURES / "simple_formulas.json").read_text())
        for case in fixtures:
            r = engine.calculate(case["formula"])
            assert_success(r, "calculate")
            assert abs(float(r["result"]) - case["expected"]) < 1e-6, (
                f"Formula {case['formula']!r}: expected {case['expected']}, got {r['result']}"
            )

    def test_empty_expression(self):
        r = engine.calculate("")
        assert_failure(r, "calculate")

    def test_malformed_expression(self):
        r = engine.calculate("2 +* 3")
        assert_failure(r, "calculate")

    def test_token_estimate_present(self):
        r = engine.calculate("1 + 1")
        assert isinstance(r["token_estimate"], int)
        assert r["token_estimate"] > 0

    def test_unsafe_input_blocked(self, monkeypatch):
        # Patch validate_ast at the module where it's called
        import _math_arithmetic
        from engine.sandbox import UnsafeExpressionError

        monkeypatch.setattr(
            _math_arithmetic, "validate_ast",
            lambda _: (_ for _ in ()).throw(UnsafeExpressionError("Lambda"))
        )
        r = engine.calculate("1 + 1")
        assert_failure(r, "calculate")

    def test_timeout(self, monkeypatch):
        import _math_arithmetic

        monkeypatch.setattr(
            _math_arithmetic, "evaluate_with_timeout",
            lambda *a, **kw: (_ for _ in ()).throw(TimeoutError("timed out"))
        )
        r = engine.calculate("2 + 2")
        assert_failure(r, "calculate")
        assert "timed out" in r["error"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# convert_units() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConvertUnits:
    def test_km_to_m(self):
        r = engine.convert_units(1.0, "kilometer", "meter")
        assert_success(r, "convert_units")
        assert r["result"] == 1000

    def test_celsius_to_kelvin(self):
        r = engine.convert_units(0.0, "degC", "kelvin")
        assert_success(r, "convert_units")
        assert abs(r["result"] - 273.15) < 0.01

    def test_unknown_unit(self):
        r = engine.convert_units(1.0, "flurps", "meter")
        assert_failure(r, "convert_units")

    def test_incompatible_units(self):
        r = engine.convert_units(1.0, "meter", "second")
        assert_failure(r, "convert_units")

    def test_empty_unit(self):
        r = engine.convert_units(1.0, "", "meter")
        assert_failure(r, "convert_units")


# ─────────────────────────────────────────────────────────────────────────────
# solve() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSolve:
    def test_linear(self):
        r = engine.solve("x - 5", "x")
        assert_success(r, "solve")
        assert "5" in str(r["result"])

    def test_quadratic(self):
        r = engine.solve("x**2 - 4", "x")
        assert_success(r, "solve")
        solutions = [str(s) for s in r["result"]]
        assert any("2" in s for s in solutions)
        assert any("-2" in s for s in solutions)

    def test_equation_with_equals(self):
        r = engine.solve("x + 3 = 7", "x")
        assert_success(r, "solve")
        assert "4" in str(r["result"])

    def test_empty_equation(self):
        r = engine.solve("", "x")
        assert_failure(r, "solve")

    def test_token_estimate(self):
        r = engine.solve("x - 1")
        assert r["token_estimate"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# simplify() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSimplify:
    def test_basic_simplify(self):
        r = engine.simplify("x**2 + 2*x + 1")
        assert_success(r, "simplify")

    def test_trig_identity(self):
        r = engine.simplify("sin(x)**2 + cos(x)**2")
        assert_success(r, "simplify")
        assert r["result"] == "1"

    def test_empty_expression(self):
        r = engine.simplify("")
        assert_failure(r, "simplify")


# ─────────────────────────────────────────────────────────────────────────────
# diff() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDiff:
    def test_polynomial(self):
        r = engine.diff("x**3", "x")
        assert_success(r, "diff")
        assert "3*x**2" in r["result"] or "3x" in r["result"]

    def test_second_order(self):
        r = engine.diff("x**3", "x", 2)
        assert_success(r, "diff")
        assert "6*x" in r["result"] or "6x" in r["result"]

    def test_trig(self):
        r = engine.diff("sin(x)", "x")
        assert_success(r, "diff")
        assert "cos(x)" in r["result"]

    def test_empty_expression(self):
        r = engine.diff("", "x")
        assert_failure(r, "diff")

    def test_invalid_order(self):
        r = engine.diff("x**2", "x", 0)
        assert_failure(r, "diff")


# ─────────────────────────────────────────────────────────────────────────────
# integrate() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegrate:
    def test_indefinite(self):
        r = engine.integrate("x**2", "x")
        assert_success(r, "integrate")
        assert "x**3" in r["result"]

    def test_definite(self):
        r = engine.integrate("x", "x", "0", "2")
        assert_success(r, "integrate")
        assert r["result"] == "2" or r["result"] == 2

    def test_trig(self):
        r = engine.integrate("cos(x)", "x")
        assert_success(r, "integrate")
        assert "sin(x)" in r["result"]

    def test_empty_expression(self):
        r = engine.integrate("", "x")
        assert_failure(r, "integrate")


# ─────────────────────────────────────────────────────────────────────────────
# describe() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDescribe:
    def test_basic(self):
        r = engine.describe([1.0, 2.0, 3.0, 4.0, 5.0])
        assert_success(r, "describe")
        assert r["result"]["mean"] == 3.0
        assert r["result"]["count"] == 5

    def test_single_value(self):
        r = engine.describe([42.0])
        assert_success(r, "describe")
        assert r["result"]["mean"] == 42.0

    def test_all_stats_present(self):
        r = engine.describe([1.0, 2.0, 3.0, 4.0, 5.0])
        assert_success(r, "describe")
        for key in ("count", "mean", "median", "std", "min", "max", "q1", "q3", "skewness", "kurtosis"):
            assert key in r["result"], f"Missing key: {key}"

    def test_empty_dataset(self):
        r = engine.describe([])
        assert_failure(r, "describe")

    def test_constrained_mode_truncation(self, monkeypatch):
        monkeypatch.setenv("MCP_CONSTRAINED_MODE", "1")
        import importlib

        import shared.platform_utils as pu
        importlib.reload(pu)
        # 150 items — should be truncated to 100 in constrained mode
        data = list(range(150))
        r = engine.describe(data)
        assert_success(r, "describe")
        assert r["result"]["count"] == 100
        importlib.reload(pu)

    def test_token_estimate(self):
        r = engine.describe([1.0, 2.0, 3.0])
        assert r["token_estimate"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# regression() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRegression:
    def test_linear_perfect(self):
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        y = [0.0, 2.0, 4.0, 6.0, 8.0]
        r = engine.regression(x, y, degree=1)
        assert_success(r, "regression")
        assert abs(r["r_squared"] - 1.0) < 1e-8
        assert abs(r["coefficients"][0] - 2.0) < 1e-8  # slope

    def test_quadratic(self):
        x = [0.0, 1.0, 2.0, 3.0]
        y = [0.0, 1.0, 4.0, 9.0]
        r = engine.regression(x, y, degree=2)
        assert_success(r, "regression")
        assert "r_squared" in r
        assert "equation" in r

    def test_length_mismatch(self):
        r = engine.regression([1.0, 2.0], [1.0, 2.0, 3.0])
        assert_failure(r, "regression")

    def test_empty_lists(self):
        r = engine.regression([], [])
        assert_failure(r, "regression")

    def test_invalid_degree(self):
        r = engine.regression([1.0, 2.0], [1.0, 2.0], degree=0)
        assert_failure(r, "regression")

    def test_too_few_points(self):
        r = engine.regression([1.0], [1.0], degree=2)
        assert_failure(r, "regression")


# ─────────────────────────────────────────────────────────────────────────────
# eval_latex() tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEvalLatex:
    def test_fraction(self):
        r = engine.eval_latex(r"\frac{10}{4}", {})
        assert_success(r, "eval_latex")
        assert abs(float(r["result"]) - 2.5) < 1e-6

    def test_with_variables(self):
        r = engine.eval_latex(r"\frac{a}{b}", {"a": 10.0, "b": 4.0})
        assert_success(r, "eval_latex")
        assert abs(float(r["result"]) - 2.5) < 1e-6

    def test_pythagorean(self):
        r = engine.eval_latex(r"\sqrt{a^{2} + b^{2}}", {"a": 3.0, "b": 4.0})
        assert_success(r, "eval_latex")
        assert abs(float(r["result"]) - 5.0) < 1e-6

    def test_fixtures(self):
        fixtures = json.loads((FIXTURES / "messy_latex.json").read_text())
        for case in fixtures:
            r = engine.eval_latex(case["formula"], case.get("variables", {}))
            assert_success(r, "eval_latex")
            assert abs(float(r["result"]) - case["expected"]) < 1e-4, (
                f"Formula {case['formula']!r}: expected {case['expected']}, got {r['result']}"
            )

    def test_empty_formula(self):
        r = engine.eval_latex("", {})
        assert_failure(r, "eval_latex")

    def test_token_estimate(self):
        r = engine.eval_latex(r"1 + 1", {})
        assert r["token_estimate"] > 0

    def test_stages_present(self):
        r = engine.eval_latex(r"\frac{1}{2}", {})
        assert_success(r, "eval_latex")
        assert "steps" in r
        assert len(r["steps"]) >= 6

    def test_unsafe_input_blocked(self, monkeypatch):
        import _math_latex
        from engine.sandbox import UnsafeExpressionError

        monkeypatch.setattr(
            _math_latex, "validate_ast",
            lambda _: (_ for _ in ()).throw(UnsafeExpressionError("Lambda"))
        )
        r = engine.eval_latex(r"\frac{1}{2}", {})
        assert_failure(r, "eval_latex")

    def test_timeout(self, monkeypatch):
        import _math_latex

        monkeypatch.setattr(
            _math_latex, "evaluate_with_timeout",
            lambda *a, **kw: (_ for _ in ()).throw(TimeoutError("timed out"))
        )
        r = engine.eval_latex(r"\frac{1}{2}", {})
        assert_failure(r, "eval_latex")
        assert "timed out" in r["error"].lower()
