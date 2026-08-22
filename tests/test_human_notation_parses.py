"""The notation the README promises must actually parse.

Every usage example the README gives for the algebra tools used caret powers
("Simplify sin(x)^2 + cos(x)^2", "the derivative of x^3 + 2x", "Integrate x^2
from 0 to 3") and all four failed. standard_transformations reads '^' as
bitwise XOR, so 'x^2' built Symbol ^ Integer and leaked a raw Python TypeError
-- "unsupported operand type(s) for ^: 'Symbol' and 'Integer'" -- to a caller
who had written the most ordinary thing in mathematics.

The same string already meant a power in eval_latex, which parses via
latex2sympy2: eval_latex("2^10") returned 1024 while calculate("2^10") failed.
One server, one string, two meanings, and no way for the caller to know which
tool spoke which dialect. These tests pin the dialect down to one.

The last class below is the load-bearing one. The obvious fix is to import
sympy's implicit_multiplication_application, but that bundle contains
split_symbols, which shatters every multi-letter name: 'velocity^2 - 4' parses
as 'c*e*i*l*o*t*v*y**2 - 4' and returns a confident wrong answer where the
unfixed code at least returned an error. A silent corruption is a worse bug
than the one being fixed, so those tests must fail if anyone ever swaps the
unpacked transformations back for the bundle.
"""

from __future__ import annotations

import pytest

import engine


def _result(response: dict) -> str:
    assert response["success"] is True, response.get("error")
    return str(response["result"])


class TestTheReadmeExamplesWork:
    """Each of these is a usage example quoted from README.md."""

    def test_simplify_a_trig_identity(self):
        assert _result(engine.simplify("sin(x)^2 + cos(x)^2")) == "1"

    def test_differentiate(self):
        assert _result(engine.diff("x^3 + 2x", "x", 1)) == "3*x**2 + 2"

    def test_second_order_derivative(self):
        assert _result(engine.diff("x^3", "x", 2)) == "6*x"

    def test_definite_integral(self):
        assert _result(engine.integrate("x^2", "x", "0", "3")) == "9"


class TestCaretIsExponentiation:
    @pytest.mark.parametrize(
        ("expression", "expected"),
        [("2^10", 1024), ("3^2 + 4^2", 25), ("(2+3)^2", 25), ("10^2", 100)],
    )
    def test_calculate_reads_caret_as_a_power(self, expression: str, expected: int):
        assert engine.calculate(expression)["result"] == expected

    def test_solve_reads_caret_as_a_power(self):
        assert engine.solve("x^2 - 5*x + 6 = 0", "x")["result"] == ["2", "3"]

    def test_every_tool_agrees_with_eval_latex(self):
        """eval_latex always read '^' as a power; now the others do too."""
        assert engine.calculate("2^10")["result"] == engine.eval_latex("2^10", {})["result"]

    def test_star_star_still_works(self):
        assert _result(engine.simplify("x**2 - 4")) == "x**2 - 4"

    def test_explicit_xor_is_still_reachable(self):
        """'^' is taken, so a caller who genuinely wants XOR names the function."""
        assert engine.simplify("Xor(a, b)")["success"] is True


class TestImplicitMultiplication:
    def test_a_coefficient_may_touch_its_variable(self):
        assert _result(engine.simplify("2x + 3x")) == "5*x"

    def test_a_coefficient_may_touch_a_bracket(self):
        assert engine.calculate("2(3+1)")["result"] == 8

    def test_a_function_power_may_be_written_before_its_argument(self):
        """sin^2 x is how the identity is written on paper."""
        assert _result(engine.simplify("cos^2 x + sin^2 x")) == "1"


class TestMultiLetterNamesSurviveIntact:
    """Guards against sympy's split_symbols, which the convenient bundle
    implicit_multiplication_application would have dragged in.

    Under that bundle every assertion here returns success=True with a
    scrambled expression, which is why they assert on the value and not just
    on success."""

    def test_a_named_quantity_is_one_symbol(self):
        assert engine.solve("velocity^2 - 4 = 0", "velocity")["result"] == ["-2", "2"]

    def test_a_product_of_named_quantities_is_not_shattered(self):
        assert _result(engine.simplify("mass*velocity^2")) == "mass*velocity**2"

    def test_dataset_column_names_survive(self):
        """These are real column names from the dataset these tools get pointed at."""
        assert _result(engine.simplify("spends + clicks")) == "clicks + spends"

    def test_a_named_quantity_substitutes_numerically(self):
        r = engine.eval_latex("velocity^2", {"velocity": 3.0})
        assert r["success"] is True, r.get("error")
        assert float(r["result"]) == 9.0
