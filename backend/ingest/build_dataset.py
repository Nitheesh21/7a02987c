"""Turn raw Elexon JSON into the clean tables the API serves. Offline step.

Findings from real samples that this module handles:
- Both streams return a plain JSON array.
- FUELHH actuals are half-hourly. WINDFOR forecasts are hourly, so each forecast is held
  across both half-hours of its hour to sit on the same grid as the actuals.
- A WINDFOR publish also lists hours that are already over at publish time. Those are not
  forecasts and are dropped.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from backend.app import config
from backend.app.selection import evaluation_frame, expected_half_hours, uk_date

ACTUALS_FILE = "actuals.csv"
FORECASTS_FILE = "forecasts.csv.gz"
QUALITY_FILE = "data_quality.json"
_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def load_raw(raw_dir: Path, prefix: str) -> pd.DataFrame:
    """Read every {prefix}_*.json file in raw_dir into one DataFrame."""
    files = sorted(raw_dir.glob(f"{prefix}_*.json"))
    if not files:
        raise FileNotFoundError(f"No {prefix}_*.json files in {raw_dir}. Run the fetch step first.")
    records: list[dict] = []
    for f in files:
        payload = json.loads(f.read_text())
        records.extend(payload["data"] if isinstance(payload, dict) else payload)
    return pd.DataFrame.from_records(records)


def build_actuals(raw: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """WIND rows only, latest publish per half-hour, delivery days start..end."""
    df = raw.copy()
    if "fuelType" in df.columns:
        df = df[df["fuelType"] == "WIND"]
    df["start_time_utc"] = pd.to_datetime(df["startTime"], utc=True)
    df["publish_time_utc"] = pd.to_datetime(df["publishTime"], utc=True)
    df = df.sort_values(["start_time_utc", "publish_time_utc"], kind="stable")
    df = df.drop_duplicates("start_time_utc", keep="last")
    df["delivery_date"] = uk_date(df["start_time_utc"])
    df = df[(df["delivery_date"] >= start) & (df["delivery_date"] <= end)]
    df = df.rename(columns={"generation": "generation_mw"})
    return df[["start_time_utc", "generation_mw", "delivery_date"]].reset_index(drop=True)


def detect_resolution_minutes(df: pd.DataFrame) -> int:
    """Gap between target times inside one publish. Only 30 and 60 are expected."""
    first_publish = df["publish_time_utc"].min()
    starts = df.loc[df["publish_time_utc"] == first_publish, "start_time_utc"]
    gaps = starts.drop_duplicates().sort_values().diff().dropna().dt.total_seconds() / 60
    if gaps.empty:
        return 30
    minutes = int(gaps.median())
    if minutes not in (30, 60):
        raise ValueError(f"Unexpected forecast resolution: {minutes} minutes")
    return minutes


def build_forecasts(raw: pd.DataFrame, start: date, end: date) -> tuple[pd.DataFrame, dict]:
    """Half-hourly forecasts with a horizon, for target days start..end.

    Returns the table and a dict of counts for the quality report.
    """
    df = raw.copy()
    df["start_time_utc"] = pd.to_datetime(df["startTime"], utc=True)
    df["publish_time_utc"] = pd.to_datetime(df["publishTime"], utc=True)
    df = df.rename(columns={"generation": "generation_mw"})
    df = df[["start_time_utc", "publish_time_utc", "generation_mw"]]
    df = df.drop_duplicates(["start_time_utc", "publish_time_utc"], keep="last")
    resolution = detect_resolution_minutes(df)
    if resolution == 60:
        second_half = df.assign(start_time_utc=df["start_time_utc"] + pd.Timedelta(minutes=30))
        df = pd.concat([df, second_half], ignore_index=True)
    df["horizon_h"] = (df["start_time_utc"] - df["publish_time_utc"]).dt.total_seconds() / 3600
    rows_before = len(df)
    df = df[df["horizon_h"] >= 0]
    dropped_past = rows_before - len(df)
    df["delivery_date"] = uk_date(df["start_time_utc"])
    df = df[(df["delivery_date"] >= start) & (df["delivery_date"] <= end)]
    df = df.sort_values(["start_time_utc", "publish_time_utc"], kind="stable")
    stats = {
        "resolution_minutes": resolution,
        "expanded_to_half_hours": resolution == 60,
        "dropped_past_targets": int(dropped_past),
    }
    return df.reset_index(drop=True), stats


def _num(value) -> float | None:
    return None if pd.isna(value) else round(float(value), 2)


def quality_report(
    actuals: pd.DataFrame,
    forecasts: pd.DataFrame,
    raw_actual_rows: int,
    raw_forecast_rows: int,
    forecast_stats: dict,
    start: date,
    end: date,
) -> dict:
    expected = expected_half_hours(start, end)
    missing = expected.difference(pd.DatetimeIndex(actuals["start_time_utc"]))
    publishes = forecasts["publish_time_utc"].drop_duplicates().sort_values()
    gaps = publishes.diff().dropna().dt.total_seconds() / 3600
    frame = evaluation_frame(forecasts, actuals, config.DEFAULT_CUTOFF, start, end)
    return {
        "window": {"delivery_start": start.isoformat(), "delivery_end": end.isoformat()},
        "actuals": {
            "raw_rows": int(raw_actual_rows),
            "rows": int(len(actuals)),
            "expected_half_hours": int(len(expected)),
            "missing_count": int(len(missing)),
            "missing_half_hours": [t.strftime(_TS_FORMAT) for t in missing[:50]],
        },
        "forecasts": {
            "raw_rows": int(raw_forecast_rows),
            "rows": int(len(forecasts)),
            "publish_count": int(len(publishes)),
            "publish_gap_hours": {
                "min": _num(gaps.min()) if len(gaps) else None,
                "median": _num(gaps.median()) if len(gaps) else None,
                "max": _num(gaps.max()) if len(gaps) else None,
            },
            "max_horizon_h": _num(forecasts["horizon_h"].max()) if len(forecasts) else None,
            **forecast_stats,
        },
        "default_cutoff": config.DEFAULT_CUTOFF.strftime("%H:%M"),
        "at_default_cutoff": {
            "forecast_coverage": _num(frame["forecast_mw"].notna().mean()),
            "mean_actual_mw": _num(frame["actual_mw"].mean()),
            "mean_forecast_mw": _num(frame["forecast_mw"].mean()),
            "mean_error_mw": _num(frame["error_mw"].mean()),
        },
    }


def build(
    raw_dir: Path = config.RAW_DIR,
    processed_dir: Path = config.PROCESSED_DIR,
    start: date = config.DELIVERY_START,
    end: date = config.DELIVERY_END,
) -> dict:
    """Read raw files, write the processed tables and the quality report. Returns the report."""
    raw_actuals = load_raw(raw_dir, "fuelhh")
    raw_forecasts = load_raw(raw_dir, "windfor")
    actuals = build_actuals(raw_actuals, start, end)
    forecasts, stats = build_forecasts(raw_forecasts, start, end)

    processed_dir.mkdir(parents=True, exist_ok=True)
    actuals.assign(start_time_utc=actuals["start_time_utc"].dt.strftime(_TS_FORMAT)).to_csv(
        processed_dir / ACTUALS_FILE, index=False
    )
    forecasts.assign(
        start_time_utc=forecasts["start_time_utc"].dt.strftime(_TS_FORMAT),
        publish_time_utc=forecasts["publish_time_utc"].dt.strftime(_TS_FORMAT),
        horizon_h=forecasts["horizon_h"].round(2),
    ).to_csv(processed_dir / FORECASTS_FILE, index=False, compression="gzip")

    quality = quality_report(
        actuals, forecasts, len(raw_actuals), len(raw_forecasts), stats, start, end
    )
    (processed_dir / QUALITY_FILE).write_text(json.dumps(quality, indent=2))
    return quality
