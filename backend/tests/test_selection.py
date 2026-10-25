from datetime import date, time

import pandas as pd

from backend.app.selection import (
    cutoff_utc,
    evaluation_frame,
    expected_half_hours,
    horizon_frame,
    select_latest,
)

NINE = time(9, 0)


def fc(rows):
    """rows: (start, publish, mw) with ISO strings."""
    return pd.DataFrame(rows, columns=["start_time_utc", "publish_time_utc", "generation_mw"])


def act(rows):
    return pd.DataFrame(rows, columns=["start_time_utc", "generation_mw"])


def test_picks_latest_publish_at_or_before_cutoff():
    f = fc(
        [
            ("2026-01-10T12:00:00Z", "2026-01-09T03:00:00Z", 100),
            ("2026-01-10T12:00:00Z", "2026-01-09T08:30:00Z", 120),
            ("2026-01-10T12:00:00Z", "2026-01-09T09:30:00Z", 150),
        ]
    )
    out = select_latest(f, NINE)
    assert len(out) == 1
    assert out.loc[0, "generation_mw"] == 120
    assert out.loc[0, "horizon_h"] == 27.5


def test_publish_exactly_at_cutoff_counts():
    f = fc(
        [
            ("2026-01-10T12:00:00Z", "2026-01-09T08:00:00Z", 110),
            ("2026-01-10T12:00:00Z", "2026-01-09T09:00:00Z", 130),
        ]
    )
    assert select_latest(f, NINE).loc[0, "generation_mw"] == 130


def test_later_forecasts_are_never_used():
    f = fc([("2026-01-10T12:00:00Z", "2026-01-09T09:30:00Z", 150)])
    assert select_latest(f, NINE).empty


def test_missing_half_hour_stays_nan_in_evaluation_frame():
    f = fc([("2026-01-10T12:00:00Z", "2026-01-09T09:30:00Z", 150)])
    a = act([("2026-01-10T12:00:00Z", 100)])
    df = evaluation_frame(f, a, NINE, date(2026, 1, 10), date(2026, 1, 10))
    assert len(df) == 48
    row = df[df["start_time_utc"] == pd.Timestamp("2026-01-10T12:00:00Z")].iloc[0]
    assert pd.isna(row["forecast_mw"])
    assert row["actual_mw"] == 100
    assert pd.isna(row["error_mw"])


def test_each_delivery_day_uses_its_own_cutoff():
    f = fc(
        [
            ("2026-01-10T12:00:00Z", "2026-01-09T08:30:00Z", 100),
            ("2026-01-10T12:00:00Z", "2026-01-10T08:30:00Z", 200),
            ("2026-01-11T12:00:00Z", "2026-01-09T08:30:00Z", 300),
            ("2026-01-11T12:00:00Z", "2026-01-10T08:30:00Z", 400),
        ]
    )
    out = select_latest(f, NINE).set_index(
        pd.DatetimeIndex(select_latest(f, NINE)["start_time_utc"])
    )
    assert out.loc["2026-01-10T12:00:00Z", "generation_mw"] == 100
    assert out.loc["2026-01-11T12:00:00Z", "generation_mw"] == 400


def test_tie_keeps_the_row_that_came_last():
    f = fc(
        [
            ("2026-01-10T12:00:00Z", "2026-01-09T08:30:00Z", 100),
            ("2026-01-10T12:00:00Z", "2026-01-09T08:30:00Z", 200),
        ]
    )
    assert select_latest(f, NINE).loc[0, "generation_mw"] == 200


def test_evaluation_frame_error_is_forecast_minus_actual():
    f = fc([("2026-01-10T12:00:00Z", "2026-01-09T08:30:00Z", 120)])
    a = act([("2026-01-10T12:00:00Z", 100)])
    df = evaluation_frame(f, a, NINE, date(2026, 1, 10), date(2026, 1, 10))
    row = df[df["forecast_mw"].notna()].iloc[0]
    assert row["error_mw"] == 20
    assert row["uk_hour"] == 12
    assert row["delivery_date"] == date(2026, 1, 10)


def test_cutoff_in_winter_is_utc():
    assert cutoff_utc(date(2026, 1, 10), NINE) == pd.Timestamp("2026-01-09T09:00:00Z")


def test_cutoff_in_summer_time_is_one_hour_earlier_in_utc():
    assert cutoff_utc(date(2026, 4, 1), NINE) == pd.Timestamp("2026-03-31T08:00:00Z")


def test_cutoff_around_spring_clock_change():
    # Clocks go forward on 29 Mar 2026. 09:00 that morning is already summer time.
    assert cutoff_utc(date(2026, 3, 30), NINE) == pd.Timestamp("2026-03-29T08:00:00Z")


def test_cutoff_around_autumn_clock_change():
    # Clocks go back on 25 Oct 2026. D-1 = 24 Oct is summer time, D-1 = 25 Oct is winter time.
    assert cutoff_utc(date(2026, 10, 25), NINE) == pd.Timestamp("2026-10-24T08:00:00Z")
    assert cutoff_utc(date(2026, 10, 26), NINE) == pd.Timestamp("2026-10-25T09:00:00Z")


def test_expected_half_hours_counts():
    assert len(expected_half_hours(date(2026, 1, 1), date(2026, 1, 31))) == 1488
    assert len(expected_half_hours(date(2026, 3, 29), date(2026, 3, 29))) == 46
    assert len(expected_half_hours(date(2026, 10, 25), date(2026, 10, 25))) == 50


def test_horizon_frame_drops_forecasts_published_after_target_and_joins_actuals():
    f = fc(
        [
            ("2026-01-10T12:00:00Z", "2026-01-09T08:30:00Z", 120),
            ("2026-01-10T12:00:00Z", "2026-01-10T12:30:00Z", 130),
        ]
    )
    a = act([("2026-01-10T12:00:00Z", 100)])
    df = horizon_frame(f, a, date(2026, 1, 10), date(2026, 1, 10))
    assert len(df) == 1
    assert df.loc[0, "horizon_h"] == 27.5
    assert df.loc[0, "error_mw"] == 20
