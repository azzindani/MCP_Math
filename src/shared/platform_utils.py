"""Platform utilities: constrained-mode detection and limit helpers."""

import os


def is_constrained_mode() -> bool:
    """Return True when MCP_CONSTRAINED_MODE=1 is set in environment."""
    return os.environ.get("MCP_CONSTRAINED_MODE", "0").strip() == "1"


def get_max_results() -> int:
    """Return max number of results to return in a single response."""
    return 10 if is_constrained_mode() else 50


def get_max_dataset_size() -> int:
    """Return max dataset length accepted by describe() and regression()."""
    return 100 if is_constrained_mode() else 10_000
