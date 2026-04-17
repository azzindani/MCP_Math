#!/usr/bin/env python3
"""CI check: all @mcp.tool() docstrings must be <= 80 characters."""

import ast
import sys
from pathlib import Path


def check_file(path: Path) -> list[str]:
    """Return list of violations found in path."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check if decorated with @mcp.tool(...)
        is_tool = any(
            (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool")
            or (isinstance(d, ast.Attribute) and d.attr == "tool")
            for d in node.decorator_list
        )
        if not is_tool:
            continue

        docstring = ast.get_docstring(node)
        if docstring is None:
            violations.append(f"{path}:{node.lineno}: {node.name}() has no docstring")
            continue

        # Docstring must be a single line and <= 80 chars
        lines = docstring.strip().splitlines()
        if len(lines) > 1:
            violations.append(
                f"{path}:{node.lineno}: {node.name}() docstring has {len(lines)} lines (max 1)"
            )
        elif len(lines[0]) > 80:
            violations.append(
                f"{path}:{node.lineno}: {node.name}() docstring is {len(lines[0])} chars (max 80): {lines[0]!r}"
            )

    return violations


def main() -> int:
    root = Path(__file__).parent.parent
    targets = [root / "src" / "server.py"]

    all_violations: list[str] = []
    for path in targets:
        if path.exists():
            all_violations.extend(check_file(path))

    if all_violations:
        print("FAIL — tool docstring violations:")
        for v in all_violations:
            print(f"  {v}")
        return 1

    print("OK — all tool docstrings are <= 80 chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
