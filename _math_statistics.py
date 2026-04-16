"""Statistics sub-module: describe() and regression()."""

from __future__ import annotations

import numpy as np
from scipy import stats as scipy_stats

from _math_helpers import (
    _error,
    build_response,
    fail,
    get_max_dataset_size,
    info,
    ok,
    warn,
)


def describe(dataset: list[float]) -> dict:
    """Compute descriptive statistics for a dataset. Returns summary."""
    op = "describe"
    progress: list[dict] = []

    if not dataset:
        return _error(op, "Empty dataset.", "Provide a non-empty list of numbers.")

    max_size = get_max_dataset_size()
    if len(dataset) > max_size:
        progress.append(warn(f"Dataset truncated from {len(dataset)} to {max_size}"))
        dataset = dataset[:max_size]

    progress.append(info(f"Computing stats for {len(dataset)} values"))

    try:
        arr = np.array(dataset, dtype=float)
    except Exception as exc:
        return _error(op, f"Invalid dataset: {exc}", "Ensure all values are numeric.", progress)

    if not np.all(np.isfinite(arr)):
        progress.append(warn("Dataset contains NaN or Inf — they will be ignored"))
        arr = arr[np.isfinite(arr)]
        if len(arr) == 0:
            return _error(op, "No finite values in dataset.", "Provide at least one finite numeric value.", progress)

    try:
        n = int(len(arr))
        mean = float(np.mean(arr))
        median = float(np.median(arr))
        std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        minimum = float(np.min(arr))
        maximum = float(np.max(arr))
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        skewness = float(scipy_stats.skew(arr)) if n > 2 else 0.0
        kurtosis = float(scipy_stats.kurtosis(arr)) if n > 3 else 0.0
    except Exception as exc:
        progress.append(fail(f"Stats error: {exc}"))
        return _error(op, f"Statistics computation failed: {exc}", "Check dataset values.", progress)

    progress.append(ok("Statistics computed"))

    stats_dict = {
        "count": n,
        "mean": mean,
        "median": median,
        "std": std,
        "min": minimum,
        "max": maximum,
        "q1": q1,
        "q3": q3,
        "skewness": skewness,
        "kurtosis": kurtosis,
    }

    return build_response(op, stats_dict, progress)


def regression(x: list[float], y: list[float], degree: int = 1) -> dict:
    """Fit polynomial regression. Returns coefficients and R-squared."""
    op = "regression"
    progress: list[dict] = []

    if not x or not y:
        return _error(op, "Empty x or y list.", "Provide matching non-empty x and y lists.")

    if len(x) != len(y):
        return _error(
            op,
            f"Length mismatch: x={len(x)}, y={len(y)}.",
            "x and y must have the same number of elements.",
        )

    max_size = get_max_dataset_size()
    if len(x) > max_size:
        progress.append(warn(f"Dataset truncated to {max_size} points"))
        x = x[:max_size]
        y = y[:max_size]

    if degree < 1:
        return _error(op, "Degree must be >= 1.", "Use degree=1 for linear, degree=2 for quadratic, etc.")

    if len(x) <= degree:
        return _error(
            op,
            f"Need at least {degree + 1} points for degree-{degree} regression, got {len(x)}.",
            "Provide more data points or reduce the degree.",
        )

    progress.append(info(f"Fitting degree-{degree} polynomial to {len(x)} points"))

    try:
        xarr = np.array(x, dtype=float)
        yarr = np.array(y, dtype=float)
        coeffs = np.polyfit(xarr, yarr, degree)
        ypred = np.polyval(coeffs, xarr)
        ss_res = float(np.sum((yarr - ypred) ** 2))
        ss_tot = float(np.sum((yarr - np.mean(yarr)) ** 2))
        r_squared = 1.0 - ss_res / ss_tot if ss_tot != 0.0 else 1.0
    except Exception as exc:
        progress.append(fail(f"Regression error: {exc}"))
        return _error(op, f"Regression failed: {exc}", "Check that x and y are numeric lists.", progress)

    coeff_list = [float(c) for c in coeffs]

    # Build human-readable equation string
    terms = []
    for i, c in enumerate(coeff_list):
        power = degree - i
        if power == 0:
            terms.append(f"{c:.6g}")
        elif power == 1:
            terms.append(f"{c:.6g}*x")
        else:
            terms.append(f"{c:.6g}*x^{power}")
    equation = " + ".join(terms)

    progress.append(ok(f"R²={r_squared:.6f}"))

    return build_response(
        op,
        coeff_list,
        progress,
        extra={
            "coefficients": coeff_list,
            "r_squared": round(r_squared, 10),
            "degree": degree,
            "equation": equation,
        },
    )


__all__ = ["describe", "regression"]
