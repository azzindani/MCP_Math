"""An answer is the number, not the last bits of the arithmetic that made it.

The sweep read float noise as answers: 100 degC -> 211.99999999999991 degF,
212 degF -> 100.00000000000006 degC, 32 degF -> 5.684341886080802e-14 degC (for
exactly 0), and calculate('0.1 + 0.2') -> 0.30000000000000004 beside a step
that said 0.300000000000000. It also read a definite integral as a STRING --
integrate('x**2', 0, 3) -> '9' -- while solve answers numbers.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine  # noqa: E402


class TestConversionsAreClean:
    @pytest.mark.parametrize(
        ("value", "source", "target", "expected"),
        [
            (100, "degC", "degF", 212),
            (212, "degF", "degC", 100),
            (32, "degF", "degC", 0),
            (-40, "degF", "degC", -40),
            (0, "degC", "K", 273.15),
            (1, "inch", "cm", 2.54),
        ],
    )
    def test_the_answer_is_the_number(self, value, source, target, expected):
        result = engine.convert_units(value, source, target)
        assert result["result"] == expected and repr(result["result"]) == repr(expected)
        assert result["to"] == f"{expected} {target}"

    def test_a_tiny_real_value_is_not_zeroed(self):
        assert engine.convert_units(1, "pm", "km")["result"] == pytest.approx(1e-15, rel=1e-12)


class TestCalculateAgreesWithItsOwnStep:
    def test_point_one_plus_point_two(self):
        result = engine.calculate("0.1 + 0.2")
        assert result["result"] == 0.3
        assert float(result["steps"][-1].split(": ")[1]) == result["result"]

    def test_a_small_number_survives(self):
        assert engine.calculate("1e-20")["result"] == pytest.approx(1e-20)


class TestADefiniteIntegralIsANumber:
    @pytest.mark.parametrize(
        ("expression", "lower", "upper", "expected"), [("x**2", "0", "3", 9), ("sin(x)", "0", "pi", 2)]
    )
    def test_a_whole_value_is_an_int(self, expression, lower, upper, expected):
        result = engine.integrate(expression, "x", lower, upper)
        assert result["result"] == expected and isinstance(result["result"], int)

    def test_an_irrational_value_keeps_its_exact_form(self):
        result = engine.integrate("1/(1+x**2)", "x", "0", "oo")
        assert result["result"] == pytest.approx(math.pi / 2)
        assert result["exact"] == "pi/2"

    def test_a_symbolic_value_stays_symbolic(self):
        assert engine.integrate("a*x", "x", "0", "1")["result"] == "a/2"

    def test_an_indefinite_integral_is_an_expression(self):
        assert engine.integrate("x**2")["result"] == "x**3/3"

    def test_a_divergent_one_is_still_labelled(self):
        result = engine.integrate("1/x", "x", "0", "1")
        assert result["result"] == "oo" and result["result_type"] == "infinite"
