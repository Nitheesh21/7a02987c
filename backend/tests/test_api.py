import json
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.data_store import DataStore
from backend.app.deps import store_dep
from backend.ingest import build_dataset as bd

START, END = date(2026, 1, 1), date(2026, 1, 3)


def _raw(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    actual_rows = []
    for t in pd.date_range("2026-01-01T00:00Z", "2026-01-03T23:30Z", freq="30min"):
        actual_rows.append(
            {
                "dataset": "FUELHH",
                "publishTime": (t + pd.Timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "startTime": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "fuelType": "WIND",
                "generation": 10000,
            }
        )
    (raw / "fuelhh_a.json").write_text(json.dumps(actual_rows))
    fc_rows = []
    for p in pd.date_range("2025-12-30T00:30Z", "2026-01-03T22:30Z", freq="2h"):
        for h in range(0, 72):
            t = p.floor("h") + pd.Timedelta(hours=h)
            if t < p:
                continue
            fc_rows.append(
                {
                    "dataset": "WINDFOR",
                    "publishTime": p.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "startTime": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    # forecast is always 500 MW above the 10000 MW actual
                    "generation": 10500,
                }
            )
    (raw / "windfor_a.json").write_text(json.dumps(fc_rows))
    return raw


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("data")
    out = tmp / "processed"
    bd.build(_raw(tmp), out, START, END)
    store = DataStore(out)
    main.app.dependency_overrides[store_dep] = lambda: store
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta(client):
    body = client.get("/api/meta").json()
    assert body["delivery_start"] == "2026-01-01"
    assert body["delivery_end"] == "2026-01-03"
    assert body["timezone"] == "Europe/London"
    assert body["data_quality"]["actuals"]["missing_count"] == 0


def test_forecast_day_uses_only_publishes_before_cutoff(client):
    body = client.get("/api/forecast", params={"delivery_date": "2026-01-02"}).json()
    assert body["cutoff_utc"] == "2026-01-01T09:00:00Z"
    assert len(body["points"]) == 48
    for p in body["points"]:
        assert p["publish_time_utc"] <= body["cutoff_utc"]
        assert p["forecast_mw"] == 10500
        assert p["actual_mw"] == 10000
        assert p["horizon_h"] > 0
    assert body["summary"]["energy_mwh"] == pytest.approx(10500 * 24)
    assert body["summary"]["coverage"] == 1.0
    # constant +500 error: the shortfall buffer is 500 MW and the band collapses onto the actual
    assert body["summary"]["p90_shortfall_buffer_mw"] == pytest.approx(500)
    assert body["points"][0]["band_low_mw"] == 10000


def test_cutoff_changes_the_forecast_used(client):
    a = client.get("/api/forecast", params={"delivery_date": "2026-01-02", "cutoff": "09:00"})
    b = client.get("/api/forecast", params={"delivery_date": "2026-01-02", "cutoff": "03:00"})
    assert a.json()["points"][0]["publish_time_utc"] > b.json()["points"][0]["publish_time_utc"]


def test_first_day_has_gaps_when_no_forecast_exists_before_cutoff(client):
    body = client.get("/api/forecast", params={"delivery_date": "2026-01-01"}).json()
    assert body["summary"]["coverage"] > 0


def test_forecast_date_outside_window_is_404(client):
    assert client.get("/api/forecast", params={"delivery_date": "2026-02-01"}).status_code == 404


def test_bad_cutoff_is_422(client):
    r = client.get("/api/forecast", params={"delivery_date": "2026-01-02", "cutoff": "9am"})
    assert r.status_code == 422
    r = client.get("/api/forecast", params={"delivery_date": "2026-01-02", "cutoff": "25:99"})
    assert r.status_code == 422


def test_days(client):
    rows = client.get("/api/forecast/days").json()
    assert [r["delivery_date"] for r in rows] == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert rows[1]["day_mae"] == pytest.approx(500)


def test_accuracy_summary(client):
    body = client.get("/api/accuracy/summary").json()
    assert body["metrics"]["bias"] == pytest.approx(500)
    assert body["metrics"]["mae"] == pytest.approx(500)
    assert body["metrics"]["nmae"] == pytest.approx(0.05)
    assert "forecast minus actual" in body["definition"]


def test_accuracy_range_validation(client):
    ok = client.get("/api/accuracy/summary", params={"start": "2026-01-02", "end": "2026-01-02"})
    assert ok.status_code == 200
    bad = client.get("/api/accuracy/summary", params={"start": "2026-01-03", "end": "2026-01-02"})
    assert bad.status_code == 422
    out = client.get("/api/accuracy/summary", params={"end": "2026-03-01"})
    assert out.status_code == 422


def test_breakdowns(client):
    assert len(client.get("/api/accuracy/by-day").json()) == 3
    hours = client.get("/api/accuracy/by-hour").json()
    assert [h["hour"] for h in hours] == list(range(24))
    horizons = client.get("/api/accuracy/by-horizon").json()
    assert horizons and horizons[0]["bucket_start_h"] == 0
    dist = client.get("/api/accuracy/distribution").json()
    assert sum(dist["histogram"]["counts"]) > 0
    assert dist["by_level"]


def test_openapi_lists_nine_routes(client):
    paths = client.get("/api/openapi.json").json()["paths"]
    assert len(paths) == 9
