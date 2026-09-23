"""All eight tools as actions of one: `math` in tools/list, not eight names.

A model reads every tool name on every turn. This server now lists one tool,
`math`, whose `action` is one of the original tools by its own name and whose
`args` object carries that tool's arguments. The action is run by the original
tool itself, so its validation and its answer are exactly what they were. The
originals leave the list and keep answering under their own names, so no
client that already calls them breaks.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import server  # noqa: E402

ORIGINALS = ["calculate", "convert_units", "solve", "simplify", "diff", "integrate", "describe", "eval_latex"]


def _listed() -> dict:
    return {t.name: t for t in asyncio.run(server.mcp.list_tools())}


def _call(tool: str, arguments: dict) -> dict:
    return asyncio.run(server.mcp._tool_manager.call_tool(tool, arguments, convert_result=False))


def _math(action: str, args: dict | None = None) -> dict:
    arguments: dict = {"action": action}
    if args is not None:
        arguments["args"] = args
    return _call("math", arguments)


class TestOneNotEight:
    def test_only_math_is_listed(self):
        assert sorted(_listed()) == ["math"]

    def test_every_original_is_exactly_one_action(self):
        actions = _listed()["math"].inputSchema["properties"]["action"]["enum"]
        assert sorted(actions) == sorted(ORIGINALS)
        assert len(actions) == len(set(actions))

    def test_the_description_names_every_action_and_its_arguments(self):
        text = _listed()["math"].description
        for name in ORIGINALS:
            assert f"- {name}:" in text
        assert "(value, from_unit, to_unit)" in text

    def test_args_refuses_what_no_action_takes(self):
        args = _listed()["math"].inputSchema["properties"]["args"]
        assert args["additionalProperties"] is False
        assert "required by convert_units" in args["properties"]["from_unit"]["description"]

    def test_it_is_read_only_like_every_action(self):
        hints = _listed()["math"].annotations
        assert hints.readOnlyHint is True and hints.destructiveHint is False

    def test_an_original_still_answers_under_its_own_name(self):
        assert set(ORIGINALS) <= set(server.mcp._tool_manager._tools)
        result = _call("calculate", {"expression": "2+2"})
        assert result["success"] is True and result["result"] == 4 and "retired" not in result


class TestAnActionIsTheOriginal:
    @pytest.mark.parametrize(
        ("action", "args"),
        [
            ("calculate", {"expression": "12*7+sqrt(81)"}),
            ("convert_units", {"value": 1, "from_unit": "km", "to_unit": "m"}),
            ("solve", {"equation": "x**2 - 9", "variable": "x"}),
            ("simplify", {"expression": "sin(x)**2 + cos(x)**2"}),
            ("diff", {"expression": "x**3", "order": 2}),
            ("integrate", {"expression": "x**2", "lower": "0", "upper": "3"}),
            ("describe", {"dataset": [1, 2, 3, 4]}),
            ("eval_latex", {"formula": "\\frac{a}{b} + c", "variables": {"a": 10, "b": 4, "c": 2}}),
        ],
    )
    def test_it_answers_what_the_original_answers(self, action, args):
        via = _math(action, args)
        direct = _call(action, args)
        assert via["success"] is True, via
        assert {k: v for k, v in via.items() if k != "token_estimate"} == {
            k: v for k, v in direct.items() if k != "token_estimate"
        }


class TestARefusalNamesTheFix:
    """Each refusal keeps the fleet's failure shape and says what to send instead."""

    @pytest.mark.parametrize(
        ("action", "args", "error_says", "hint_says"),
        [
            ("calculate", {"expr": "1"}, "expr", "expression"),
            ("solve", {}, "solve", "equation"),
            ("describe", {"dataset": "abc"}, "describe", "dataset"),
            ("differentiate", {"expression": "x"}, "differentiate", "diff"),
        ],
    )
    def test_a_wrong_call_is_shaped_and_pointed(self, action, args, error_says, hint_says):
        result = _math(action, args)
        assert result["success"] is False
        assert set(result) >= {"op", "error", "hint", "token_estimate"}
        assert error_says in result["error"]
        assert hint_says in result["hint"]

    def test_an_undeclared_top_level_argument_is_refused(self):
        result = _call("math", {"action": "calculate", "args": {"expression": "1"}, "expresion": "1"})
        assert result["success"] is False and "expresion" in result["error"]
