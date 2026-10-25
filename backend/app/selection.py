"""Latest-before-cutoff forecast selection. Pure functions, no file or network access."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from backend.app.config import UK_TZ

_UK = ZoneInfo(UK_TZ)
_NS_UTC = "datetime64[ns, UTC]"


def _ns(series: pd.Series) -> pd.Series:
    """Normalise a timestamp column to tz-aware UTC at nanosecond resolution."""
    return pd.to_datetime(series, utc=True).astype(_NS_UTC)


def uk_date(series: pd.Series) -> pd.Series:
    """UK local calendar date of each UTC timestamp."""
    return series.dt.tz_convert(UK_TZ).dt.date


def cutoff_utc(delivery_date: date, cutoff: time) -> pd.Timestamp:
    """The cutoff on D-1 at HH:MM UK time, as a UTC timestamp."""
    local = datetime.combine(delivery_date - timedelta(days=1), cutoff, tzinfo=_UK)
    return pd.Timestamp(local).tz_convert("UTC")


def expected_half_hours(start: date, end: date) -> pd.DatetimeIndex:
    """Every half-hour of UK days start..end inclusive, in UTC. 46 or 50 on clock-change days."""
    first = pd.Timestamp(start).tz_localize(UK_TZ)
    stop = pd.Timestamp(end + timedelta(days=1)).tz_localize(UK_TZ)
    return pd.date_range(first, stop, freq="30min", inclusive="left").tz_convert("UTC")


def select_latest(forecasts: pd.DataFrame, cutoff: time) -> pd.DataFrame:
    """For each target half-hour keep the forecast with the latest publish time at or before
    the cutoff on D-1. Later forecasts are never used. Half-hours with no qualifying forecast
    are absent from the result.

    Input columns: start_time_utc, publish_time_utc, generation_mw.
    Output columns: those three plus delivery_date and horizon_h (hours from publish to start).
    """
    df = forecasts[["start_time_utc", "publish_time_utc", "generation_mw"]].copy()
    df["start_time_utc"] = _ns(df["start_time_utc"])
    df["publish_time_utc"] = _ns(df["publish_time_utc"])
    df["delivery_date"] = uk_date(df["start_time_utc"])
    cutoffs = {d: cutoff_utc(d, cutoff) for d in df["delivery_date"].unique()}
    df["cutoff_utc"] = _ns(df["delivery_date"].map(cutoffs))
    df = df[df["publish_time_utc"] <= df["cutoff_utc"]]
    # Stable sort, so if two rows tie the one that came last in the input is kept.
    df = df.sort_values(["start_time_utc", "publish_time_utc"], kind="stable")
    df = df.drop_duplicates("start_time_utc", keep="last")
    df["horizon_h"] = (df["start_time_utc"] - df["publish_time_utc"]).dt.total_seconds() / 3600
    return df.drop(columns="cutoff_utc").reset_index(drop=True)


def evaluation_frame(
    forecasts: pd.DataFrame, actuals: pd.DataFrame, cutoff: time, start: date, end: date
) -> pd.DataFrame:
    """One row per half-hour of UK days start..end, with the chosen forecast and the actual.
    Missing values stay NaN so gaps show up instead of being hidden.

    Columns: start_time_utc, publish_time_utc, forecast_mw, horizon_h, actual_mw, error_mw,
    delivery_date, uk_hour. Error is forecast minus actual.
    """
    base = pd.DataFrame({"start_time_utc": _ns(pd.Series(expected_half_hours(start, end)))})
    chosen = select_latest(forecasts, cutoff).rename(columns={"generation_mw": "forecast_mw"})
    chosen = chosen[["start_time_utc", "publish_time_utc", "forecast_mw", "horizon_h"]]
    act = actuals[["start_time_utc", "generation_mw"]].rename(
        columns={"generation_mw": "actual_mw"}
    )
    act = act.assign(start_time_utc=_ns(act["start_time_utc"]))
    df = base.merge(chosen, on="start_time_utc", how="left").merge(
        act, on="start_time_utc", how="left"
    )
    df["error_mw"] = df["forecast_mw"] - df["actual_mw"]
    df["delivery_date"] = uk_date(df["start_time_utc"])
    df["uk_hour"] = df["start_time_utc"].dt.tz_convert(UK_TZ).dt.hour
    return df


def horizon_frame(
    forecasts: pd.DataFrame, actuals: pd.DataFrame, start: date, end: date
) -> pd.DataFrame:
    """Every forecast (all publish times) for UK days start..end joined to its actual.
    Forecasts published after their target time are dropped. Independent of the cutoff.

    Columns: start_time_utc, publish_time_utc, forecast_mw, horizon_h, actual_mw, error_mw.
    """
    f = forecasts[["start_time_utc", "publish_time_utc", "generation_mw"]].rename(
        columns={"generation_mw": "forecast_mw"}
    )
    f = f.assign(
        start_time_utc=_ns(f["start_time_utc"]), publish_time_utc=_ns(f["publish_time_utc"])
    )
    local_day = uk_date(f["start_time_utc"])
    f = f[(local_day >= start) & (local_day <= end)].copy()
    f["horizon_h"] = (f["start_time_utc"] - f["publish_time_utc"]).dt.total_seconds() / 3600
    f = f[f["horizon_h"] >= 0]
    act = actuals[["start_time_utc", "generation_mw"]].rename(
        columns={"generation_mw": "actual_mw"}
    )
    act = act.assign(start_time_utc=_ns(act["start_time_utc"]))
    df = f.merge(act, on="start_time_utc", how="inner")
    df["error_mw"] = df["forecast_mw"] - df["actual_mw"]
    return df.reset_index(drop=True)
