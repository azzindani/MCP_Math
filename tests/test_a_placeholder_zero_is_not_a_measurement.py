"""Undefined statistics must come back as null, not as a convenient zero.

describe() substituted 0.0 for every statistic its sample was too small to
support:

    std      = np.std(arr, ddof=1) if n > 1 else 0.0
    skewness = scipy_stats.skew(arr) if n > 2 else 0.0
    kurtosis = scipy_stats.kurtosis(arr) if n > 3 else 0.0

Each of those zeros is a specific claim -- std 0.0 says the values do not
vary, skewness 0.0 says the distribution is perfectly symmetric, excess
kurtosis 0.0 says its tails match a normal's -- and all three are claims the
data cannot support. This is worse than NaN, which at least reads as absent: a
caller has no way to tell a measured zero from a placeholder.

regression() had the sharper version of the same thing. With every y identical
the R-squared ratio is 0/0, and the fallback was 1.0 -- announcing that the fit
explains all of the variance in the one case where there is none to explain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import engine  # noqa: E402

# --- describe ---------------------------------------------------------------


def test_a_single_value_has_no_spread_to_report():
    r = engine.describe([42.0])
    assert r["success"] is True
    stats = r["result"]
    assert stats["count"] == 1
    assert stats["mean"] == 42.0
    # None, not 0.0: one value does not have a standard deviation of zero.
    assert stats["std"] is None
    assert stats["skewness"] is None
    assert stats["kurtosis"] is None
    assert set(stats["undefined"]) == {"std", "skewness", "kurtosis"}
    assert "dataset has 1" in stats["undefined"]["std"]


@pytest.mark.parametrize(
    ("n", "expected_undefined"),
    [
        (1, {"std", "skewness", "kurtosis"}),
        (2, {"skewness", "kurtosis"}),
        (3, {"kurtosis"}),
        (4, set()),
    ],
)
def test_each_statistic_appears_at_its_own_minimum(n, expected_undefined):
    r = engine.describe([float(i) for i in range(1, n + 1)] if n > 1 else [7.0])
    stats = r["result"]
    assert set(stats.get("undefined", {})) == expected_undefined
    for name in ("std", "skewness", "kurtosis"):
        if name in expected_undefined:
            assert stats[name] is None, name
        else:
            assert isinstance(stats[name], float), name


def test_a_genuinely_flat_dataset_still_reports_zero_spread():
    """Five identical values do have a standard deviation, and it is 0.

    Their skewness and kurtosis do not: both divide by that zero. scipy says
    NaN, which is right and is not something JSON can carry.
    """
    stats = engine.describe([7.0] * 5)["result"]
    assert stats["std"] == 0.0
    assert stats["skewness"] is None
    assert stats["kurtosis"] is None
    assert "no spread" in stats["undefined"]["skewness"]
    # Not the small-sample reason -- five values is plenty.
    assert "needs at least" not in stats["undefined"]["skewness"]


def test_a_real_dataset_is_unchanged():
    stats = engine.describe([1.0, 2.0, 3.0, 10.0])["result"]
    assert stats["count"] == 4
    assert stats["std"] == pytest.approx(4.0824829, rel=1e-6)
    assert stats["skewness"] == pytest.approx(1.0182338, rel=1e-6)
    assert stats["kurtosis"] == pytest.approx(-0.7696, rel=1e-6)
    assert "undefined" not in stats


def test_the_warning_names_what_is_missing():
    """The progress line lists which statistics; the `undefined` map says why.

    Why differs per statistic -- too few values, or no spread among them -- so
    a single reason in the warning would be wrong for one of the two cases.
    """
    r = engine.describe([42.0])
    warnings = [p["message"] for p in r["progress"] if p["level"] == "warn"]
    assert any("undefined" in m and "std" in m and "skewness" in m for m in warnings), warnings


# --- regression -------------------------------------------------------------


def test_a_flat_y_has_no_variance_to_explain():
    r = engine.regression([1.0, 2.0, 3.0], [5.0, 5.0, 5.0])
    assert r["success"] is True
    # The bug: this was 1.0, a perfect fit reported for the one case where the
    # measure is undefined.
    assert r["r_squared"] is None
    assert "no variance" in r["r_squared_undefined"]
    # The fit itself is still real and still returned.
    assert len(r["coefficients"]) == 2
    assert r["equation"]


def test_a_perfect_fit_on_varying_y_still_reports_one():
    r = engine.regression([1.0, 2.0, 3.0], [2.0, 4.0, 6.0])
    assert r["r_squared"] == pytest.approx(1.0)
    assert "r_squared_undefined" not in r


def test_a_partial_fit_reports_its_real_share():
    r = engine.regression([1.0, 2.0, 3.0, 4.0], [1.0, 3.0, 2.0, 5.0])
    assert 0.0 < r["r_squared"] < 1.0
    assert "r_squared_undefined" not in r


def test_token_estimate_survives_the_null_fields():
    for r in (engine.describe([42.0]), engine.regression([1.0, 2.0, 3.0], [5.0, 5.0, 5.0])):
        assert isinstance(r["token_estimate"], int)
        assert r["token_estimate"] > 0


# --- what a response is allowed to contain ----------------------------------


def test_no_response_carries_a_token_json_cannot_write():
    """`json.dumps` emits bare NaN and Infinity, which no parser must accept.

    Several clients read those back as numbers anyway, so an undefined
    statistic would arrive at the far end looking like a measurement.
    """
    responses = [
        engine.describe([42.0]),
        engine.describe([7.0] * 5),
        engine.regression([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]),
        engine.calculate("1/0"),
        engine.calculate("oo"),
    ]
    for r in responses:
        json.dumps(r, allow_nan=False)  # raises ValueError on NaN or Infinity


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("oo", "oo"),
        ("-oo", "-oo"),
        ("1/0", "zoo"),
    ],
)
def test_an_infinite_result_comes_back_as_its_symbol(expression, expected):
    """calculate("oo") raised OverflowError out of the tool.

    `int(numeric)` was evaluated before the `abs(numeric) < 1e15` guard meant
    to keep it in range, so the conversion ran on infinity. The exception
    escaped the tool entirely, past the contract that says none propagate to
    server.py -- and OverflowError was not among the three the handler caught.
    """
    r = engine.calculate(expression)
    assert r["success"] is True
    assert r["result"] == expected


def test_an_ordinary_result_is_still_a_number():
    assert engine.calculate("2+2")["result"] == 4
    assert engine.calculate("10**20")["result"] == 1e20
    assert engine.calculate("1/3")["result"] == pytest.approx(0.33333333, rel=1e-6)
