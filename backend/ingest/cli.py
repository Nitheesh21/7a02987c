"""Command line for the offline data step.

python -m backend.ingest.cli fetch   # download raw JSON into data/raw/
python -m backend.ingest.cli build   # clean and write data/processed/
python -m backend.ingest.cli all     # both
"""

from __future__ import annotations

import argparse
import json
from datetime import timedelta

import httpx

from backend.app import config
from backend.ingest import build_dataset
from backend.ingest.elexon_client import fetch_fuelhh, fetch_windfor, save_raw


def run_fetch(fuelhh_chunk_days: int, windfor_chunk_days: int) -> None:
    start, end = config.DELIVERY_START, config.DELIVERY_END
    publish_from = start - timedelta(days=config.FORECAST_LEAD_DAYS)
    with httpx.Client() as client:
        for name, records in fetch_fuelhh(client, start, end, fuelhh_chunk_days):
            save_raw(name, records, config.RAW_DIR)
            print(f"{name}: {len(records)} rows")
        for name, records in fetch_windfor(client, publish_from, end, windfor_chunk_days):
            save_raw(name, records, config.RAW_DIR)
            print(f"{name}: {len(records)} rows")


def run_build() -> None:
    quality = build_dataset.build()
    print(json.dumps(quality, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m backend.ingest.cli")
    parser.add_argument("command", choices=["fetch", "build", "all"])
    parser.add_argument("--fuelhh-chunk-days", type=int, default=7)
    parser.add_argument("--windfor-chunk-days", type=int, default=3)
    args = parser.parse_args(argv)
    if args.command in ("fetch", "all"):
        run_fetch(args.fuelhh_chunk_days, args.windfor_chunk_days)
    if args.command in ("build", "all"):
        run_build()


if __name__ == "__main__":
    main()
