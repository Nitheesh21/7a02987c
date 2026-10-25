import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from backend.app import metrics


def test_error_metrics_on_hand_computed_values():
    # errors are +10, -10, 0
    m = metrics.error_metrics([110, 90, 100], [100, 100, 100])
    assert m["count"] == 3
    assert m["bias"] == pytest.approx(0.0)
    assert m["mae"] == pytest.approx(20 / 3)
    assert m["rmse"] == pytest.approx(math.sqrt(200 / 3))
    assert m["nmae"] == pytest.approx((20 / 3) / 100)
    assert m["p90_abs_error"] == pytest.approx(10.0)
    assert m["p95_abs_error"] == pytest.approx(10.0)
    # 90th percentile of [-10, 0, 10] is 8.0
    assert m["p90_shortfall_buffer_mw"] == pytest.approx(8.0)


def test_empty_input_gives_count_zero_and_none():
    m = metrics.error_metrics([], [])
    assert m["count"] == 0
    assert m["mae"] is None
    assert m["p90_shortfall_buffer_mw"] is None


def test_nan_pairs_are_dropped():
    m = metrics.error_metrics([110, np.nan, 90], [100, 100, np.nan])
    assert m["count"] == 1
    assert m["bias"] == pytest.approx(10.0)


def test_buffer_is_floored_at_zero_when_forecast_is_always_low():
    m = metrics.error_metrics([95, 90, 80], [100, 100, 100])
    assert m["p90_shortfall_buffer_mw"] == 0.0
    assert m["bias"] < 0


def test_nmae_is_none_when_mean_actual_is_zero():
    assert metrics.error_metrics([5, 5], [0, 0])["nmae"] is None


def test_error_band_percentiles():
    actual = np.zeros(21)
    forecast = np.linspace(-10, 10, 21)
    low, high = metrics.error_band(forecast, actual)
    assert low == pytest.approx(-8.0)
    assert high == pytest.approx(8.0)
    assert metrics.error_band([], []) == (None, None)


def test_histogram_counts_add_up():
    h = metrics.error_histogram(np.arange(50), np.zeros(50), bins=10)
    assert sum(h["counts"]) == 50
    assert len(h["edges"]) == 11
    assert metrics.error_histogram([], []) == {"edges": [], "counts": []}


def _frame():
    return pd.DataFrame(
        {
            "delivery_date": [date(2026, 1, 1)] * 2 + [date(2026, 1, 2)] * 2,
            "uk_hour": [0, 1, 0, 1],
            "forecast_mw": [110.0, 120.0, 100.0, np.nan],
            "actual_mw": [100.0, 100.0, 100.0, 100.0],
            "horizon_h": [20.0, 20.5, 26.0, np.nan],
        }
    )


def test_by_day_and_by_hour_ignore_incomplete_rows():
    df = _frame()
    days = metrics.by_day(df)
    assert [d["date"] for d in days] == ["2026-01-01", "2026-01-02"]
    assert days[0]["mae"] == pytest.approx(15.0)
    assert days[0]["bias"] == pytest.approx(15.0)
    assert days[1]["count"] == 1
    hours = metrics.by_hour(df)
    assert [h["hour"] for h in hours] == [0, 1]
    assert hours[0]["count"] == 2


def test_by_horizon_buckets():
    out = metrics.by_horizon(_frame())
    assert [r["bucket"] for r in out] == ["18-24h", "24-30h"]
    assert out[0]["count"] == 2


def test_by_level_quartiles_cover_all_complete_rows():
    df = pd.DataFrame({"forecast_mw": np.arange(1.0, 9.0), "actual_mw": np.arange(1.0, 9.0) - 1})
    out = metrics.by_level(df)
    assert [r["quartile"] for r in out] == [1, 2, 3, 4]
    assert sum(r["count"] for r in out) == 8
    assert all(r["bias"] == pytest.approx(1.0) for r in out)


def test_day_summary_energy_is_half_of_summed_mw():
    df = pd.DataFrame({"forecast_mw": [100.0, 100.0, np.nan], "horizon_h": [20.0, 21.0, np.nan]})
    s = metrics.day_summary(df, buffer_mw=5.0)
    assert s["energy_mwh"] == pytest.approx(100.0)
    assert s["peak_mw"] == 100.0
    assert s["avg_horizon_h"] == pytest.approx(20.5)
    assert s["coverage"] == pytest.approx(2 / 3)
    assert s["p90_shortfall_buffer_mw"] == 5.0


def test_coverage_needs_both_forecast_and_actual():
    assert metrics.coverage(_frame()) == pytest.approx(0.75)
