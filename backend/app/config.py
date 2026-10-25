"""Settings: pilot window, default cutoff and file locations."""

import os
from datetime import date, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", ROOT / "data" / "processed"))

UK_TZ = "Europe/London"


def parse_hhmm(value: str) -> time:
    """Parse 'HH:MM' into a time. Raises ValueError on bad input."""
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


# Pilot window: delivery days 1 to 31 Jan 2026 (confirmed). Each decision is made on D-1.
DELIVERY_START = date.fromisoformat(os.getenv("DELIVERY_START", "2026-01-01"))
DELIVERY_END = date.fromisoformat(os.getenv("DELIVERY_END", "2026-01-31"))

# Forecasts are fetched from this many days before the first delivery day, so the earliest
# decisions (made on D-1 of the first day) have forecasts to choose from.
FORECAST_LEAD_DAYS = 5

# Assumed day-ahead gate time, adjustable by the user in the app.
DEFAULT_CUTOFF = parse_hhmm(os.getenv("DEFAULT_CUTOFF", "09:00"))
