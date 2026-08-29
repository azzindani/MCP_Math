"""A result that is not a number must not arrive as a successful number.

calculate("1/0") returned {"success": true, "result": "zoo"}. The contract (§7)
says `success` is the first key the model checks, and §1 says the model is a
dispatcher and this server the sole executor -- so "zoo", "nan" and "-oo" under
a true flag get read as values, or replaced with an invented number.

describe() already had this exact problem and was fixed to report `null` plus an
`undefined` block naming the reason. These are the same discipline for the three
tools that return a single computed value.
"""

from __future__ import annotations

import pytest

import engine

# --- no value at all: these must fail, not succeed with a symbol -------------


@pytest.mark.parametrize(
    "expression",
    [
        "1/0",  # zoo -- division by zero
        "0/0",  # nan -- indeterminate
        "(1/0) + 1",  # zoo survives arithmetic
    ],
)
def test_an_expression_with_no_value_is_not_a_success(expression):
    result = engine.calculate(expression)

    assert result["success"] is False, f"{expression} reported success with result {result.get('result')!r}"
    assert "error" in result and "hint" in result
    assert "result" not in result, "a failed call must not also carry a result"


def test_the_failure_names_the_reason_and_points_somewhere():
    result = engine.calculate("1/0")

    assert "divides by zero" in result["error"]
    # §8: a hint must name a specific tool or fix, never "try again".
    assert "solve()" in result["hint"] or "simplify()" in result["hint"]


def test_a_divergent_integral_is_not_a_successful_integration():
    # The Cauchy principal value is 0, but the integral does not converge;
    # sympy returns nan and this used to come back as success with "nan".
    result = engine.integrate("1/x", "x", "-1", "1")

    assert result["success"] is False
    assert "converge" in result["hint"]


def test_a_latex_formula_that_divides_by_zero_is_not_a_success():
    result = engine.eval_latex(r"\frac{1}{x - x}", {"x": 5})

    assert result["success"] is False
    assert "divides by zero" in result["error"]


# --- a real answer that is not a finite real: succeed, but say so ------------


def test_infinity_is_an_answer_but_is_labelled_as_one():
    result = engine.calculate("log(0)")

    assert result["success"] is True
    assert result["result_type"] == "infinite"
    assert "not a value to compute with" in result["note"]


def test_a_complex_result_is_an_answer_but_is_labelled_as_one():
    result = engine.calculate("sqrt(-1)")

    assert result["success"] is True
    assert result["result_type"] == "complex"


def test_an_ordinary_number_carries_no_such_label():
    result = engine.calculate("2 + 3 * 4")

    assert result["success"] is True
    assert result["result"] == 14
    assert "result_type" not in result
    assert "note" not in result


def test_a_symbolic_integral_is_untouched():
    # An indefinite integral has free symbols. It is not a number and was never
    # meant to be one, so it must not be classified or annotated.
    result = engine.integrate("x**2", "x")

    assert result["success"] is True
    assert result["result"] == "x**3/3"
    assert "result_type" not in result


# --- the OverflowError that escaped eval_latex entirely ---------------------


def test_latex_infinity_does_not_raise_out_of_the_tool():
    # Stage 6 ran int(numeric) before the magnitude guard meant to protect it,
    # and OverflowError was not caught: eval_latex(r"\infty") raised straight
    # past the error contract. calculate() was fixed for this; this was not.
    result = engine.eval_latex(r"\infty")

    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["result_type"] == "infinite"


def test_every_tool_still_returns_a_dict_for_these_inputs():
    # §7: every tool returns a dict, no exceptions.
    for call in (
        lambda: engine.calculate("1/0"),
        lambda: engine.calculate("oo"),
        lambda: engine.integrate("1/x", "x", "-1", "1"),
        lambda: engine.eval_latex(r"\infty"),
        lambda: engine.eval_latex(r"\frac{1}{x - x}", {"x": 5}),
    ):
        out = call()
        assert isinstance(out, dict)
        assert isinstance(out["success"], bool)
        assert isinstance(out["token_estimate"], int)
