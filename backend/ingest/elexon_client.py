"""Download FUELHH (WIND only) and WINDFOR from the Elexon Insights stream endpoints.

Run offline, once. The web app never calls Elexon. No API key is needed.
Both streams return a plain JSON array. A {"data": [...]} wrapper is also accepted.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import httpx

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
FUELHH_PATH = "/datasets/FUELHH/stream"
WINDFOR_PATH = "/datasets/WINDFOR/stream"


def day_chunks(start: date, end: date, days: int) -> Iterator[tuple[date, date]]:
    """Split start..end (inclusive) into consecutive windows of at most `days` days."""
    cursor = start
    while cursor <= end:
        stop = min(cursor + timedelta(days=days - 1), end)
        yield cursor, stop
        cursor = stop + timedelta(days=1)


def _records(payload) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raise ValueError(f"Unexpected response shape: {type(payload).__name__}")


def get_records(client: httpx.Client, path: str, params: dict, retries: int = 4) -> list[dict]:
    """GET one stream window. Retries rate limits, server errors and network errors."""
    for attempt in range(retries + 1):
        try:
            response = client.get(BASE_URL + path, params=params, timeout=60)
            response.raise_for_status()
            return _records(response.json())
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code != 429 and code < 500:
                raise RuntimeError(
                    f"Elexon rejected {path} {params}: HTTP {code} {exc.response.text[:300]}"
                ) from exc
            if attempt == retries:
                raise
        except (httpx.TransportError, ValueError):
            if attempt == retries:
                raise
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


def fetch_fuelhh(
    client: httpx.Client, start: date, end: date, chunk_days: int = 7
) -> Iterator[tuple[str, list[dict]]]:
    """Actual wind output by settlement date, filtered to fuelType WIND."""
    for a, b in day_chunks(start, end, chunk_days):
        params = {
            "settlementDateFrom": a.isoformat(),
            "settlementDateTo": b.isoformat(),
            "fuelType": "WIND",
        }
        yield f"fuelhh_{a}_{b}", get_records(client, FUELHH_PATH, params)


def fetch_windfor(
    client: httpx.Client, publish_from: date, publish_to: date, chunk_days: int = 3
) -> Iterator[tuple[str, list[dict]]]:
    """Wind forecasts by publish time. Chunk edges overlap by one instant, build dedupes."""
    for a, b in day_chunks(publish_from, publish_to, chunk_days):
        params = {
            "publishDateTimeFrom": f"{a.isoformat()}T00:00Z",
            "publishDateTimeTo": f"{(b + timedelta(days=1)).isoformat()}T00:00Z",
        }
        yield f"windfor_{a}_{b}", get_records(client, WINDFOR_PATH, params)


def save_raw(name: str, records: list[dict], raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{name}.json"
    path.write_text(json.dumps(records))
    return path
