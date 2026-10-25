"""Forecast error metrics and breakdowns. Pure functions, no file or network access.

Error is forecast minus actual, in MW. A positive error means less wind than forecast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HORIZON_BUCKET_H = 6
_EMPTY = {
    "count": 0,
    "bias": None,
    "mae": None,
    "rmse": None,
    "nmae": None,
    "p90_abs_error": None,
    "p95_abs_error": None,
    "p90_shortfall_buffer_mw": None,
}


def _pair(forecast, actual) -> tuple[np.ndarray, np.ndarray]:
    """Return forecast and actual arrays with any pair containing a NaN removed."""
    f = np.asarray(forecast, dtype=float)
    a = np.asarray(actual, dtype=float)
    keep = ~(np.isnan(f) | np.isnan(a))
    return f[keep], a[keep]


def error_metrics(forecast, actual) -> dict:
    """Bias, MAE, RMSE, nMAE, percentile errors and the P90 shortfall buffer."""
    f, a = _pair(forecast, actual)
    if f.size == 0:
        return dict(_EMPTY)
    e = f - a
    abs_e = np.abs(e)
    mae = float(abs_e.mean())
    mean_actual = float(a.mean())
    return {
        "count": int(f.size),
        "bias": float(e.mean()),
        "mae": mae,
        "rmse": float(np.sqrt((e**2).mean())),
        "nmae": mae / mean_actual if mean_actual > 0 else None,
        "p90_abs_error": float(np.percentile(abs_e, 90)),
        "p95_abs_error": float(np.percentile(abs_e, 95)),
        "p90_shortfall_buffer_mw": float(max(0.0, np.percentile(e, 90))),
    }


def error_band(forecast, actual) -> tuple[float | None, float | None]:
    """P10 and P90 of the error. The 80% band for actual output is [f - P90, f - P10]."""
    f, a = _pair(forecast, actual)
    if f.size == 0:
        return None, None
    e = f - a
    return float(np.percentile(e, 10)), float(np.percentile(e, 90))


def error_histogram(forecast, actual, bins: int = 20) -> dict:
    """Histogram of the error: bin edges (bins + 1 values) and counts."""
    f, a = _pair(forecast, actual)
    if f.size == 0:
        return {"edges": [], "counts": []}
    counts, edges = np.histogram(f - a, bins=bins)
    return {"edges": [float(x) for x in edges], "counts": [int(c) for c in counts]}


def coverage(df: pd.DataFrame) -> float:
    """Share of half-hours that have both a forecast and an actual."""
    if len(df) == 0:
        return 0.0
    return float(df[["forecast_mw", "actual_mw"]].notna().all(axis=1).mean())


def _complete(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna(subset=["forecast_mw", "actual_mw"])


def _row(g: pd.DataFrame) -> dict:
    m = error_metrics(g["forecast_mw"], g["actual_mw"])
    return {"count": m["count"], "mae": m["mae"], "bias": m["bias"]}


def by_day(df: pd.DataFrame) -> list[dict]:
    d = _complete(df)
    return [{"date": k.isoformat(), **_row(g)} for k, g in d.groupby("delivery_date", sort=True)]


def by_hour(df: pd.DataFrame) -> list[dict]:
    d = _complete(df)
    return [{"hour": int(k), **_row(g)} for k, g in d.groupby("uk_hour", sort=True)]


def by_horizon(df: pd.DataFrame, bucket_h: int = HORIZON_BUCKET_H) -> list[dict]:
    """Error by forecast horizon bucket, for a frame from selection.horizon_frame."""
    d = _complete(df)
    if d.empty:
        return []
    start = (np.floor(d["horizon_h"] / bucket_h) * bucket_h).astype(int)
    rows = []
    for k, g in d.groupby(start, sort=True):
        rows.append({"bucket": f"{k}-{k + bucket_h}h", "bucket_start_h": int(k), **_row(g)})
    return rows


def by_level(df: pd.DataFrame) -> list[dict]:
    """Error by forecast level, in quartiles of forecast MW."""
    d = _complete(df)
    if d.empty:
        return []
    quartile = pd.qcut(d["forecast_mw"].rank(method="first"), 4, labels=False)
    rows = []
    for k, g in d.groupby(quartile, sort=True):
        rows.append(
            {
                "quartile": int(k) + 1,
                "forecast_min_mw": float(g["forecast_mw"].min()),
                "forecast_max_mw": float(g["forecast_mw"].max()),
                **_row(g),
            }
        )
    return rows


def day_summary(df: pd.DataFrame, buffer_mw: float | None) -> dict:
    """Headline numbers for one delivery day. Energy is MW times 0.5 hours per half-hour."""
    f = df["forecast_mw"]
    has_forecast = bool(f.notna().any())
    h = df["horizon_h"]
    return {
        "energy_mwh": float(f.sum() * 0.5) if has_forecast else None,
        "peak_mw": float(f.max()) if has_forecast else None,
        "min_mw": float(f.min()) if has_forecast else None,
        "avg_mw": float(f.mean()) if has_forecast else None,
        "avg_horizon_h": float(h.mean()) if h.notna().any() else None,
        "p90_shortfall_buffer_mw": buffer_mw,
        "coverage": float(f.notna().mean()) if len(df) else 0.0,
    }
