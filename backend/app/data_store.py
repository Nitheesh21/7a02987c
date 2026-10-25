"""Loads the processed tables once and serves cached evaluation frames."""

from __future__ import annotations

import json
from datetime import date, time
from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend.app import config
from backend.app.selection import evaluation_frame, horizon_frame, uk_date

_REQUIRED = ("actuals.csv", "forecasts.csv.gz", "data_quality.json")


class DataNotFoundError(RuntimeError):
    pass


class DataStore:
    def __init__(self, processed_dir: Path = config.PROCESSED_DIR):
        missing = [f for f in _REQUIRED if not (processed_dir / f).exists()]
        if missing:
            raise DataNotFoundError(
                f"Missing {missing} in {processed_dir}. Run: python -m backend.ingest.cli all"
            )
        self.actuals = pd.read_csv(processed_dir / "actuals.csv")
        self.actuals["start_time_utc"] = pd.to_datetime(self.actuals["start_time_utc"], utc=True)
        self.forecasts = pd.read_csv(processed_dir / "forecasts.csv.gz")
        for col in ("start_time_utc", "publish_time_utc"):
            self.forecasts[col] = pd.to_datetime(self.forecasts[col], utc=True)
        self.quality: dict = json.loads((processed_dir / "data_quality.json").read_text())
        window = self.quality["window"]
        self.start = date.fromisoformat(window["delivery_start"])
        self.end = date.fromisoformat(window["delivery_end"])
        self._eval = lru_cache(maxsize=64)(self._build_eval)
        self._horizon: pd.DataFrame | None = None

    def _build_eval(self, cutoff: time) -> pd.DataFrame:
        return evaluation_frame(self.forecasts, self.actuals, cutoff, self.start, self.end)

    def evaluation(self, cutoff: time) -> pd.DataFrame:
        return self._eval(cutoff)

    def horizons(self) -> pd.DataFrame:
        if self._horizon is None:
            self._horizon = horizon_frame(self.forecasts, self.actuals, self.start, self.end)
        return self._horizon

    def last_publish(self) -> pd.Timestamp | None:
        return self.forecasts["publish_time_utc"].max() if len(self.forecasts) else None

    def window_days(self) -> list[date]:
        return [d.date() for d in pd.date_range(self.start, self.end)]


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    return DataStore()


def delivery_dates(df: pd.DataFrame) -> pd.Series:
    return uk_date(df["start_time_utc"])
