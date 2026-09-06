"""`calculate(expression=123)` answered with a pydantic dump and a URL.

Round 28 sent one required string parameter as an int on every endpoint in the
fleet. Twenty-two returned the fleet's failure shape. Four did not -- browser,
docs-read, docs-edit and math -- and they are exactly the four repos that never
received `shared/arg_errors.py`:

    Error executing tool calculate: 1 validation error for calculateArguments
    expression
      Input should be a valid string [type=string_type, input_value=123, input_type=int]
        For further information visit https://errors.pydantic.dev/2.13/v/string_type

No `success` to branch on, no `hint`, and a link to the internet from a server
built to run offline.

`integrate` is the sharpest case here, because its bounds are STRINGS on
purpose. `lower=""` is a third state -- no bound, meaning an indefinite
integral -- which a number cannot express. Office documents the same tri-state
convention for `bold` in its docstrings and explains it again on failure; math
did neither, so the obvious call `integrate("2*x", "x", lower=0, upper=3)`
failed with the raw dump and no advice. The docstring now says it, and the
refusal now has the fleet's shape.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _as_text(result) -> str:
    for attr in ("structured_content", "content"):
        value = getattr(result, attr, None)
        if value is not None:
            if isinstance(value, dict):
                return json.dumps(value)
            return json.dumps([getattr(c, "text", str(c)) for c in value])
    return json.dumps(result) if isinstance(result, (dict, list)) else str(result)


def _call(tool: str, args: dict) -> str:
    import server

    return _as_text(asyncio.run(server.mcp._tool_manager.call_tool(tool, args)))


@pytest.mark.parametrize(
    "tool,args",
    [
        ("calculate", {"expression": 123}),
        ("describe", {"dataset": "notalist"}),
        ("integrate", {"expression": "2*x", "variable": "x", "lower": 0, "upper": 3}),
    ],
)
def test_a_wrong_type_stays_inside_the_contract(tool, args):
    text = _call(tool, args)
    assert "success" in text, text[:400]
    assert "pydantic.dev" not in text, "an offline server sent the caller to the internet"


def test_the_refusal_names_the_argument():
    assert "expression" in _call("calculate", {"expression": 123})


def test_the_unknown_name_guard_still_answers_first():
    text = _call("calculate", {"definitely_not_a_parameter": 1})
    assert "definitely_not_a_parameter" in text and "does not take" in text


class TestTheBoundsAreQuotedOnPurpose:
    def test_quoted_bounds_give_a_definite_integral(self):
        from src import engine

        r = engine.integrate("2*x", "x", "0", "3")
        assert r["success"] is True
        assert str(r["result"]) == "9"

    def test_no_bounds_give_an_indefinite_one(self):
        """This is the third state a plain number could not express."""
        from src import engine

        r = engine.integrate("2*x", "x", "", "")
        assert r["success"] is True
        assert r["type"] == "indefinite"

    def test_the_docstring_says_the_bounds_are_strings(self):
        import server

        doc = server.integrate.__doc__ or ""
        assert "string" in doc.lower(), doc
        assert '"0"' in doc or "'0'" in doc, doc
