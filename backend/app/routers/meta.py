from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app import config
from backend.app.data_store import DataStore
from backend.app.deps import store_dep
from backend.app.schemas import Health, Meta

router = APIRouter()


@router.get("/health", response_model=Health, summary="Liveness check")
def health() -> Health:
    return Health(status="ok")


@router.get("/meta", response_model=Meta, summary="Window, defaults and data quality report")
def meta(store: DataStore = Depends(store_dep)) -> Meta:
    last = store.last_publish()
    return Meta(
        delivery_start=store.start.isoformat(),
        delivery_end=store.end.isoformat(),
        default_cutoff=config.DEFAULT_CUTOFF.strftime("%H:%M"),
        timezone=config.UK_TZ,
        last_forecast_publish_utc=last.strftime("%Y-%m-%dT%H:%M:%SZ") if last is not None else None,
        data_quality=store.quality,
    )
