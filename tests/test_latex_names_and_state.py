"""eval_latex could not do the thing it exists for, and broke itself doing it.

Both defects were found by a full-coverage sweep, then isolated here.

1. State pollution. latex2sympy2 keeps its symbol tables in module globals and
   rebinds one of them -- `var` -- to a bare Symbol partway through a failing
   parse. Every later call then does a membership test against that Symbol,
   which is where "argument of type 'Symbol' is not iterable" comes from. So one
   malformed formula disabled eval_latex for the lifetime of the process. On a
   long-running server that means the tool stays broken until it is restarted,
   and the error names neither the caller's formula nor the real cause.

2. Named quantities. latex2sympy cannot parse a multi-letter name at all, so
   \\frac{spends}{clicks} failed whether or not values were supplied -- it broke
   in the parser, before substitution could happen. That is the documented use
   case for this tool (CLAUDE.md 6.5: a formula plus a variables map), so the
   names are now bound into the formula text before parsing and the parser only
   ever sees numbers.

The hint for an unbound formula also said "Check LaTeX syntax", which for a
perfectly valid formula is worse than no hint: it sends the caller to inspect
something that is not the problem.
"""

from __future__ import annotations

import pytest

import engine


class TestNamedQuantities:
    def test_the_documented_use_case(self):
        result = engine.eval_latex(r"\frac{spends}{clicks}", {"spends": 100.0, "clicks": 8.0})
        assert result["success"] is True
        assert float(result["result"]) == 12.5

    def test_underscored_names(self):
        result = engine.eval_latex(r"\frac{click_rate}{clicks}", {"click_rate": 10.0, "clicks": 4.0})
        assert result["success"] is True
        assert float(result["result"]) == 2.5

    def test_a_longer_name_is_not_corrupted_by_a_shorter_one(self):
        """Binding "click" before "click_rate" would rewrite half the longer
        name and leave a syntactically broken formula behind."""
        result = engine.eval_latex(r"\frac{click_rate}{click}", {"click": 2.0, "click_rate": 10.0})
        assert result["success"] is True
        assert float(result["result"]) == 5.0

    def test_names_inside_a_function(self):
        result = engine.eval_latex(r"\sqrt{area}", {"area": 16.0})
        assert result["success"] is True
        assert float(result["result"]) == 4.0

    def test_single_letters_still_work(self):
        result = engine.eval_latex(r"\frac{a}{b}", {"a": 1.0, "b": 2.0})
        assert result["success"] is True
        assert float(result["result"]) == 0.5

    def test_a_plain_numeric_formula_is_untouched(self):
        result = engine.eval_latex(r"\frac{1}{2}")
        assert result["success"] is True
        assert float(result["result"]) == 0.5

    def test_a_latex_command_is_never_treated_as_a_name(self):
        """A variable called "frac" must not rewrite \\frac into a number."""
        result = engine.eval_latex(r"\frac{1}{2}", {"frac": 99.0})
        assert result["success"] is True
        assert float(result["result"]) == 0.5


class TestUnboundNamesAreExplained:
    def test_the_hint_names_the_missing_quantities(self):
        result = engine.eval_latex(r"\frac{spends}{clicks}")
        assert result["success"] is False
        assert "spends" in result["hint"]
        assert "clicks" in result["hint"]

    def test_the_hint_points_at_variables_not_at_the_syntax(self):
        """The formula is valid LaTeX; telling the caller to check its syntax
        sends them to inspect something that is not wrong."""
        result = engine.eval_latex(r"\frac{spends}{clicks}")
        assert "variables" in result["hint"]

    def test_a_genuinely_malformed_formula_still_gets_the_syntax_hint(self):
        result = engine.eval_latex(r"\frac{")
        assert result["success"] is False
        assert "syntax" in result["hint"].lower()


class TestParserStateSurvivesFailure:
    def test_one_bad_formula_does_not_break_the_next_good_one(self):
        engine.eval_latex(r"\frac{spends}{clicks}")
        result = engine.eval_latex(r"\frac{a}{b}", {"a": 1.0, "b": 2.0})
        assert result["success"] is True, "a failed parse poisoned the parser"
        assert float(result["result"]) == 0.5

    def test_repeated_failures_do_not_accumulate(self):
        """On a long-running server the failures are not going to arrive singly."""
        for _ in range(20):
            engine.eval_latex(r"\frac{spends}{clicks}")
        result = engine.eval_latex(r"\frac{1}{4}")
        assert result["success"] is True
        assert float(result["result"]) == 0.25

    def test_the_parser_globals_are_left_as_they_were_found(self):
        l2s = pytest.importorskip("latex2sympy2")
        before = type(getattr(l2s, "var", None))
        engine.eval_latex(r"\frac{spends}{clicks}")
        assert type(getattr(l2s, "var", None)) is before, "latex2sympy2.var was left clobbered"
