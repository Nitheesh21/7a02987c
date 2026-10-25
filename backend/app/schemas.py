"""Response models. They double as the API documentation at /api/docs."""

from __future__ import annotations

from pydantic import BaseModel


class Metrics(BaseModel):
    count: int
    bias: float | None = None
    mae: float | None = None
    rmse: float | None = None
    nmae: float | None = None
    p90_abs_error: float | None = None
    p95_abs_error: float | None = None
    p90_shortfall_buffer_mw: float | None = None


class Health(BaseModel):
    status: str


class Meta(BaseModel):
    delivery_start: str
    delivery_end: str
    default_cutoff: str
    timezone: str
    last_forecast_publish_utc: str | None
    data_quality: dict


class ForecastPoint(BaseModel):
    start_time_utc: str
    uk_time: str
    forecast_mw: float | None
    actual_mw: float | None
    publish_time_utc: str | None
    horizon_h: float | None
    band_low_mw: float | None
    band_high_mw: float | None


class DaySummary(BaseModel):
    energy_mwh: float | None
    peak_mw: float | None
    min_mw: float | None
    avg_mw: float | None
    avg_horizon_h: float | None
    p90_shortfall_buffer_mw: float | None
    coverage: float


class ForecastResponse(BaseModel):
    delivery_date: str
    cutoff_utc: str
    cutoff_uk: str
    summary: DaySummary
    points: list[ForecastPoint]


class ForecastDay(DaySummary):
    delivery_date: str
    day_mae: float | None


class SummaryResponse(BaseModel):
    cutoff: str
    start: str
    end: str
    metrics: Metrics
    coverage: float
    error_band_p10_mw: float | None
    error_band_p90_mw: float | None
    band_coverage: float | None
    definition: str


class Histogram(BaseModel):
    edges: list[float]
    counts: list[int]


class Distribution(BaseModel):
    histogram: Histogram
    by_level: list[dict]
