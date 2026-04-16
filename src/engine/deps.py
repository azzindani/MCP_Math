"""DAG builder and topological sort for formula dependency resolution."""

from __future__ import annotations

import re


def build_dag(variables: dict[str, str | float]) -> dict[str, set[str]]:
    """Build a dependency graph from a variable dict.

    String values that reference other keys are treated as edges.
    Float/int values have no dependencies.

    Args:
        variables: Mapping of variable name -> value (float) or sub-formula (str).

    Returns:
        Dict mapping each key to the set of keys it depends on.
    """
    keys = set(variables.keys())
    dag: dict[str, set[str]] = {k: set() for k in keys}

    for name, value in variables.items():
        if isinstance(value, str):
            # Find all identifiers in the formula string
            refs = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", value))
            # Only track dependencies on other known variables
            dag[name] = refs & keys - {name}

    return dag


def topological_sort(dag: dict[str, set[str]]) -> list[str]:
    """Return keys in evaluation order (dependencies first).

    Args:
        dag: Dependency graph from build_dag().

    Returns:
        List of keys ordered so each key appears after its dependencies.

    Raises:
        ValueError: If the dependency graph contains a cycle.
    """
    order: list[str] = []
    visited: set[str] = set()
    in_stack: set[str] = set()

    def visit(node: str) -> None:
        if node in in_stack:
            raise ValueError(f"Circular dependency detected involving '{node}'")
        if node in visited:
            return
        in_stack.add(node)
        for dep in dag.get(node, set()):
            visit(dep)
        in_stack.discard(node)
        visited.add(node)
        order.append(node)

    for key in dag:
        visit(key)

    return order
