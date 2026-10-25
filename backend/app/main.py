"""FastAPI app. Read-only: serves precomputed Elexon data, never calls Elexon."""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.routers import accuracy, forecast, meta

app = FastAPI(
    title="UK national wind forecast: day-ahead decision view",
    version="1.0.0",
    description="Latest wind forecast at the day-ahead cutoff, and how accurate it has been. "
    "Data: Elexon BMRS FUELHH (actuals) and WINDFOR (forecasts).",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
for r in (meta.router, forecast.router, accuracy.router):
    app.include_router(r, prefix="/api")
