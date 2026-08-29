"""eval_latex could not do the thing it exists for, and broke itself doing it.

Both defects were found by a full-coverage sweep, then isolated here.

1. State pollution. latex2sympy2 kept its symbol tables in module globals and
   rebound one of them -- `var` -- to a bare Symbol partway through a failing
   parse. Every later call then did a membership test against that Symbol,
   which is where "argument of type 'Symbol' is not iterable" came from. So one
   malformed formula disabled eval_latex for the lifetime of the process. On a
   long-running server that means the tool stays broken until it is restarted,
   and the error names neither the caller's formula nor the real cause.
   latex2sympy2 has since been dropped -- it pinned an antlr4 runtime that
   cannot import on Python 3.13+ -- but the behaviour it broke is still the
   contract, so these tests stay: a parser is free to be stateless, and this
   proves the one in use is.

2. Named quantities. Neither parser reads \\frac{spends}{clicks} as two names:
   latex2sympy2 broke outright, and SymPy reads a multi-letter name as a product
   of single letters (s*p*e*n*ds). That is the documented use case for this tool
   (CLAUDE.md 6.5: a formula plus a variables map), so supplied names are bound
   into the formula text before parsing and the parser only ever sees numbers.
   A name left unbound is reported as the caller wrote it, not as the letters it
   was shredded into.

The hint for an unbound formula also said "Check LaTeX syntax", which for a
perfectly valid formula is worse than no hint: it sends the caller to inspect
something that is not the problem.
"""

from __future__ import annotations

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

    def test_an_unbound_name_is_reported_as_written(self):
        """SymPy parses \\frac{spends}{clicks} as s*p*e*n*ds over c*l*i*c*k*s, so
        the symbols left standing are nine letters the caller never typed and
        neither of the two they did. Report the formula's names, not the
        parser's."""
        result = engine.eval_latex(r"\frac{spends}{clicks}")
        assert result["success"] is False
        assert "clicks, spends" in result["error"], result["error"]

    def test_an_unbound_single_letter_is_still_reported(self):
        """The name scan deliberately ignores single letters, so this is the one
        case that must fall back to the parser's own symbols."""
        result = engine.eval_latex(r"\frac{a}{b}")
        assert result["success"] is False
        assert "a" in result["hint"] and "b" in result["hint"]

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
