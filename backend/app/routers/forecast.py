from __future__ import annotations

from datetime import date, time

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app import config, metrics
from backend.app.data_store import DataStore
from backend.app.deps import cutoff_dep, store_dep
from backend.app.schemas import ForecastDay, ForecastResponse
from backend.app.selection import cutoff_utc

router = APIRouter(prefix="/forecast")
_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _num(x) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), 1)


def _buffer_and_band(df: pd.DataFrame) -> tuple[float | None, float | None, float | None]:
    m = metrics.error_metrics(df["forecast_mw"], df["actual_mw"])
    p10, p90 = metrics.error_band(df["forecast_mw"], df["actual_mw"])
    return m["p90_shortfall_buffer_mw"], p10, p90


@router.get("", response_model=ForecastResponse, summary="Latest forecast for one delivery day")
def forecast_for_day(
    delivery_date: date = Query(..., description="Delivery day D (UK local date)."),
    cutoff: time = Depends(cutoff_dep),
    store: DataStore = Depends(store_dep),
) -> ForecastResponse:
    """For each half-hour of D: the forecast with the latest publish time at or before the
    cutoff on D-1. Actuals are shown only to compare, never used to choose the forecast."""
    if not store.start <= delivery_date <= store.end:
        raise HTTPException(
            status_code=404, detail=f"Delivery date outside {store.start} to {store.end}"
        )
    full = store.evaluation(cutoff)
    buffer_mw, p10, p90 = _buffer_and_band(full)
    day = full[full["delivery_date"] == delivery_date]
    points = []
    for r in day.itertuples():
        f = _num(r.forecast_mw)
        has_band = f is not None and p10 is not None and p90 is not None
        points.append(
            {
                "start_time_utc": r.start_time_utc.strftime(_FMT),
                "uk_time": r.start_time_utc.tz_convert(config.UK_TZ).strftime("%H:%M"),
                "forecast_mw": f,
                "actual_mw": _num(r.actual_mw),
                "publish_time_utc": None
                if pd.isna(r.publish_time_utc)
                else r.publish_time_utc.strftime(_FMT),
                "horizon_h": _num(r.horizon_h),
                "band_low_mw": round(f - p90, 1) if has_band else None,
                "band_high_mw": round(f - p10, 1) if has_band else None,
            }
        )
    c = cutoff_utc(delivery_date, cutoff)
    return ForecastResponse(
        delivery_date=delivery_date.isoformat(),
        cutoff_utc=c.strftime(_FMT),
        cutoff_uk=c.tz_convert(config.UK_TZ).strftime("%Y-%m-%d %H:%M %Z"),
        summary=metrics.day_summary(day, buffer_mw),
        points=points,
    )


@router.get("/days", response_model=list[ForecastDay], summary="One summary row per delivery day")
def forecast_days(
    cutoff: time = Depends(cutoff_dep), store: DataStore = Depends(store_dep)
) -> list[ForecastDay]:
    full = store.evaluation(cutoff)
    buffer_mw, _, _ = _buffer_and_band(full)
    mae_by_day = {r["date"]: r["mae"] for r in metrics.by_day(full)}
    out = []
    for d, g in full.groupby("delivery_date", sort=True):
        out.append(
            ForecastDay(
                delivery_date=d.isoformat(),
                day_mae=_num(mae_by_day.get(d.isoformat())),
                **metrics.day_summary(g, buffer_mw),
            )
        )
    return out
