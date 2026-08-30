"""solve() returned its roots as strings. JSON has numbers.

Found by round 22's sweep, whose axis was to judge each response as DATA rather
than as prose: `solve("x^2 - 4 = 0")` answered `["-2", "2"]` -- two integers
delivered as text. Nothing failed, every check passed, and the caller had to
parse the answer back out of a string that no other tool in this server
produces.

The cause was one line. `solve` did `[str(s) for s in solutions]` *before*
handing the list to `build_response`, so `engine/formatter._serialize` -- which
already returns an int for a whole value, a float for a real one, and the
symbol only where there is no number -- never saw a SymPy object at all.

Two tests in test_human_notation_parses.py asserted the string form, so the
defect had test coverage confirming it. That is the thing to notice: a test can
lock a defect in place as firmly as it can catch one.
"""

from __future__ import annotations

import json

import engine


def _numbers(equation: str, variable: str = "x") -> list:
    payload = engine.solve(equation, variable)
    assert payload["success"], payload
    return payload["result"]


class TestRootsAreNumbers:
    def test_integer_roots_are_json_integers(self):
        assert _numbers("x**2 - 4 = 0") == [-2, 2]
        assert all(isinstance(v, int) for v in _numbers("x**2 - 4 = 0"))

    def test_a_linear_equation_answers_with_a_number(self):
        assert _numbers("2*x + 6 = 0") == [-3]

    def test_an_irrational_root_is_a_real_float(self):
        """sqrt(2) has a numeric value, so it is given as one.

        The distinction that matters is "no numeric value", not "not an
        integer" -- an irrational root is still a number.
        """
        roots = _numbers("x**2 - 2 = 0")
        assert all(isinstance(v, float) for v in roots)
        assert roots[1] == pytest_approx(2**0.5)

    def test_the_result_survives_a_strict_json_round_trip(self):
        """No NaN, no Infinity, no repr -- the round-22 contract."""

        def reject(constant: str) -> None:
            raise AssertionError(f"non-JSON literal {constant} in the response")

        payload = engine.solve("x**2 - 4 = 0", "x")
        json.loads(json.dumps(payload), parse_constant=reject)


class TestSymbolicRootsStaySymbolic:
    """A root with no finite real value has no number to give.

    These must NOT be forced into floats. `I` is not 0.0, and a complex root
    silently flattened to a real one is a worse answer than a string.
    """

    def test_complex_roots_are_strings(self):
        assert _numbers("x**2 + 1 = 0") == ["-I", "I"]

    def test_a_mixed_answer_says_that_it_is_mixed(self):
        """One real root and two complex ones, in one list.

        A caller iterating this list meets an int and then a str. The response
        says so rather than leaving it to be discovered by a type error.
        """
        payload = engine.solve("x**3 - 8 = 0", "x")
        assert payload["result"][0] == 2
        assert payload["symbolic_solutions"] == 2
        assert "symbolic" in payload["note"]

    def test_an_all_numeric_answer_carries_no_note(self):
        """The note costs tokens, so it appears only when it is true."""
        payload = engine.solve("x**2 - 4 = 0", "x")
        assert "note" not in payload
        assert "symbolic_solutions" not in payload


def pytest_approx(value: float, tol: float = 1e-9):
    class _Approx:
        def __eq__(self, other: object) -> bool:
            return isinstance(other, (int, float)) and abs(float(other) - value) < tol

        def __repr__(self) -> str:  # pragma: no cover - only shown on failure
            return f"approx({value})"

    return _Approx()
