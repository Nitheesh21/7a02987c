"""Shared request parsing for the routers."""

from __future__ import annotations

from datetime import date, time

from fastapi import Depends, HTTPException, Query

from backend.app import config
from backend.app.data_store import DataNotFoundError, DataStore, get_store


def store_dep() -> DataStore:
    try:
        return get_store()
    except DataNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def cutoff_dep(
    cutoff: str = Query(
        config.DEFAULT_CUTOFF.strftime("%H:%M"),
        pattern=r"^\d{2}:\d{2}$",
        description="Day-ahead cutoff on D-1, UK local time, HH:MM.",
    ),
) -> time:
    try:
        return config.parse_hhmm(cutoff)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid cutoff '{cutoff}'") from exc


def range_dep(
    store: DataStore = Depends(store_dep),
    start: date | None = Query(None, description="First delivery date, default window start."),
    end: date | None = Query(None, description="Last delivery date, default window end."),
) -> tuple[date, date]:
    s, e = start or store.start, end or store.end
    if s > e:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    if s < store.start or e > store.end:
        raise HTTPException(
            status_code=422, detail=f"Dates must be within {store.start} to {store.end}"
        )
    return s, e
