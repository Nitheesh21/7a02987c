"""Tests for the offline build step. Row values are copied from real Elexon samples
(FUELHH 1 to 2 Jan 2026, WINDFOR published 31 Dec 2025), plus clearly marked synthetic rows
that exercise the filters."""

import json
from datetime import date

import pandas as pd

from backend.ingest import build_dataset as bd


def fuelhh(start, publish, mw, fuel="WIND"):
    return {
        "dataset": "FUELHH",
        "publishTime": publish,
        "startTime": start,
        "settlementDate": start[:10],
        "settlementPeriod": 1,
        "fuelType": fuel,
        "generation": mw,
    }


def windfor(start, publish, mw):
    return {"dataset": "WINDFOR", "publishTime": publish, "startTime": start, "generation": mw}


ACTUAL_ROWS = [
    fuelhh("2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z", 13756),
    fuelhh("2026-01-01T23:00:00Z", "2026-01-01T23:30:00Z", 15578),
    fuelhh("2026-01-01T23:30:00Z", "2026-01-02T00:00:00Z", 15538),
    # synthetic: a later revision of the same half-hour, a non-wind row, a row before the window
    fuelhh("2026-01-01T23:30:00Z", "2026-01-02T01:00:00Z", 15540),
    fuelhh("2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z", 1, fuel="CCGT"),
    fuelhh("2025-12-31T23:30:00Z", "2026-01-01T00:00:00Z", 1),
]

HOURLY_FORECAST_ROWS = [
    windfor("2025-12-31T03:00:00Z", "2025-12-31T04:30:00Z", 8191),
    windfor("2025-12-31T04:00:00Z", "2025-12-31T04:30:00Z", 8771),
    windfor("2025-12-31T05:00:00Z", "2025-12-31T04:30:00Z", 9722),
    windfor("2025-12-31T06:00:00Z", "2025-12-31T04:30:00Z", 10146),
]


def test_actuals_keep_wind_latest_publish_and_window():
    out = bd.build_actuals(pd.DataFrame(ACTUAL_ROWS), date(2026, 1, 1), date(2026, 1, 1))
    assert len(out) == 3
    by_start = out.set_index(out["start_time_utc"].dt.strftime("%H:%M"))["generation_mw"]
    assert by_start["00:00"] == 13756
    assert by_start["23:30"] == 15540


def test_hourly_forecast_is_held_across_both_half_hours_and_past_targets_dropped():
    out, stats = bd.build_forecasts(
        pd.DataFrame(HOURLY_FORECAST_ROWS), date(2025, 12, 31), date(2026, 1, 31)
    )
    assert stats["resolution_minutes"] == 60
    assert stats["expanded_to_half_hours"] is True
    assert stats["dropped_past_targets"] == 3
    assert out["horizon_h"].min() == 0.0
    assert list(out["generation_mw"]) == [8771, 9722, 9722, 10146, 10146]


def test_half_hourly_forecast_is_not_expanded():
    rows = [
        windfor("2026-01-10T00:00:00Z", "2026-01-09T08:30:00Z", 100),
        windfor("2026-01-10T00:30:00Z", "2026-01-09T08:30:00Z", 110),
        windfor("2026-01-10T01:00:00Z", "2026-01-09T08:30:00Z", 120),
    ]
    out, stats = bd.build_forecasts(pd.DataFrame(rows), date(2026, 1, 10), date(2026, 1, 10))
    assert stats["resolution_minutes"] == 30
    assert len(out) == 3


def test_duplicate_forecast_rows_are_removed():
    rows = [
        windfor("2026-01-10T00:00:00Z", "2026-01-09T08:30:00Z", 100),
        windfor("2026-01-10T00:00:00Z", "2026-01-09T08:30:00Z", 100),
        windfor("2026-01-10T00:30:00Z", "2026-01-09T08:30:00Z", 110),
    ]
    out, _ = bd.build_forecasts(pd.DataFrame(rows), date(2026, 1, 10), date(2026, 1, 10))
    assert len(out) == 2


def test_build_writes_files_and_quality_report(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "fuelhh_a.json").write_text(json.dumps(ACTUAL_ROWS))
    forecasts = [
        windfor("2026-01-01T00:00:00Z", "2025-12-31T04:30:00Z", 19556),
        windfor("2026-01-01T01:00:00Z", "2025-12-31T04:30:00Z", 19707),
        windfor("2026-01-01T00:00:00Z", "2025-12-31T02:30:00Z", 19512),
        windfor("2026-01-01T01:00:00Z", "2025-12-31T02:30:00Z", 19664),
    ]
    (raw / "windfor_a.json").write_text(json.dumps({"data": forecasts}))
    out = tmp_path / "processed"
    quality = bd.build(raw, out, date(2026, 1, 1), date(2026, 1, 1))
    assert (out / bd.ACTUALS_FILE).exists()
    assert (out / bd.FORECASTS_FILE).exists()
    assert json.loads((out / bd.QUALITY_FILE).read_text())["actuals"]["rows"] == 3
    assert quality["actuals"]["expected_half_hours"] == 48
    assert quality["actuals"]["missing_count"] == 45
    assert quality["forecasts"]["rows"] == 8
    assert quality["forecasts"]["resolution_minutes"] == 60
    assert quality["forecasts"]["publish_count"] == 2
    reloaded = pd.read_csv(out / bd.FORECASTS_FILE)
    assert set(reloaded.columns) == {
        "start_time_utc",
        "publish_time_utc",
        "generation_mw",
        "horizon_h",
        "delivery_date",
    }
