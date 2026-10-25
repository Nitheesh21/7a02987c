from __future__ import annotations

from datetime import date, time

from fastapi import APIRouter, Depends

from backend.app import metrics
from backend.app.data_store import DataStore
from backend.app.deps import cutoff_dep, range_dep, store_dep
from backend.app.schemas import Distribution, SummaryResponse
from backend.app.selection import horizon_frame

router = APIRouter(prefix="/accuracy")

DEFINITION = (
    "Error = forecast minus actual, in MW. Positive means less wind than forecast, "
    "so the buyer may be short. Forecast = latest publish at or before the cutoff on D-1."
)


def _slice(store: DataStore, cutoff: time, rng: tuple[date, date]):
    df = store.evaluation(cutoff)
    return df[(df["delivery_date"] >= rng[0]) & (df["delivery_date"] <= rng[1])]


@router.get("/summary", response_model=SummaryResponse, summary="Headline accuracy numbers")
def summary(
    cutoff: time = Depends(cutoff_dep),
    rng: tuple[date, date] = Depends(range_dep),
    store: DataStore = Depends(store_dep),
) -> SummaryResponse:
    df = _slice(store, cutoff, rng)
    m = metrics.error_metrics(df["forecast_mw"], df["actual_mw"])
    p10, p90 = metrics.error_band(df["forecast_mw"], df["actual_mw"])
    band_cov = None
    if p10 is not None:
        both = df.dropna(subset=["forecast_mw", "actual_mw"])
        inside = (both["actual_mw"] >= both["forecast_mw"] - p90) & (
            both["actual_mw"] <= both["forecast_mw"] - p10
        )
        band_cov = float(inside.mean())
    return SummaryResponse(
        cutoff=cutoff.strftime("%H:%M"),
        start=rng[0].isoformat(),
        end=rng[1].isoformat(),
        metrics=m,
        coverage=metrics.coverage(df),
        error_band_p10_mw=p10,
        error_band_p90_mw=p90,
        band_coverage=band_cov,
        definition=DEFINITION,
    )


@router.get("/by-day", summary="Error by delivery day")
def by_day(
    cutoff: time = Depends(cutoff_dep),
    rng: tuple[date, date] = Depends(range_dep),
    store: DataStore = Depends(store_dep),
) -> list[dict]:
    return metrics.by_day(_slice(store, cutoff, rng))


@router.get("/by-hour", summary="Error by UK hour of day")
def by_hour(
    cutoff: time = Depends(cutoff_dep),
    rng: tuple[date, date] = Depends(range_dep),
    store: DataStore = Depends(store_dep),
) -> list[dict]:
    return metrics.by_hour(_slice(store, cutoff, rng))


@router.get("/by-horizon", summary="Error by forecast horizon (all publish times)")
def by_horizon(
    rng: tuple[date, date] = Depends(range_dep), store: DataStore = Depends(store_dep)
) -> list[dict]:
    """Uses every forecast, not only the one chosen at the cutoff, so it shows how accuracy
    changes as the target time gets closer. It does not depend on the cutoff."""
    df = horizon_frame(store.forecasts, store.actuals, rng[0], rng[1])
    return metrics.by_horizon(df)


@router.get("/distribution", response_model=Distribution, summary="Error histogram and levels")
def distribution(
    cutoff: time = Depends(cutoff_dep),
    rng: tuple[date, date] = Depends(range_dep),
    store: DataStore = Depends(store_dep),
) -> Distribution:
    df = _slice(store, cutoff, rng)
    return Distribution(
        histogram=metrics.error_histogram(df["forecast_mw"], df["actual_mw"]),
        by_level=metrics.by_level(df),
    )
