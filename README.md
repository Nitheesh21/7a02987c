# Wind Forecast Accuracy Portal

A web app for a UK power buyer. It shows the latest national wind forecast that was available when a day-ahead purchase had to be made, and it measures how accurate those forecasts have been.

- **Pilot window:** delivery days 1 to 31 January 2026. Each decision is made on the day before, so decision dates run from 31 December 2025 to 30 January 2026.
- **Data:** Elexon BMRS only. FUELHH for actual wind output, WINDFOR for wind forecasts. No other data is used.

## Links

- Live app: TODO (Vercel URL)
- Demo video (unlisted): TODO (YouTube URL)

## What it does

1. **Decision view:** pick a delivery day and a cutoff time on the day before. The app shows the latest forecast for each half-hour that had been published by then, an error band, and a procurement buffer.
2. **Accuracy view:** quantifies forecast error over the pilot window with MAE, RMSE, bias, percentile errors, and breakdowns by day, hour of day, forecast horizon and forecast level.
3. **Method page:** plain-language definitions of the cutoff rule and every metric.

## Quick start with Docker

```bash
git clone <repo-url>
cd <repo-name>
docker compose up --build
```

- App: http://localhost:8080
- API docs: http://localhost:8000/api/docs

The processed data is committed to the repo, so no internet access or API key is needed to run the app.

## Run without Docker

Needs Python 3.12 or newer and Node 20 or newer.

```bash
# Backend
pip install -r requirements-dev.txt
uvicorn backend.app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `localhost:8000`.

## Refresh the data

Only needed if you want to re-fetch from Elexon. Needs internet access. No API key is required.

```bash
python -m backend.ingest.cli fetch   # download raw JSON into data/raw/ (7-day FUELHH and 3-day WINDFOR windows)
python -m backend.ingest.cli build   # clean and write data/processed/
python -m backend.ingest.cli all     # both steps
```

## Tests

```bash
pytest                      # backend
cd frontend && npm test     # frontend
```

## Repository layout

```
README.md               this file
vercel.json             Vercel build, rewrites, included data files
requirements.txt        Python runtime dependencies (Vercel and Docker)
requirements-dev.txt    test and lint dependencies
docker-compose.yml      api (8000) and web (8080) services
api/index.py            Vercel entry point, exposes the FastAPI app
backend/
  Dockerfile
  app/
    main.py             FastAPI app, docs at /api/docs
    config.py           paths, pilot window, default cutoff
    schemas.py          response models
    data_store.py       loads processed data once, caches per cutoff
    deps.py             cutoff and date-range validation
    selection.py        latest-before-cutoff logic (pure functions)
    metrics.py          error metrics and breakdowns (pure functions)
    routers/            meta, forecast, accuracy
  ingest/
    elexon_client.py    chunked, retrying fetch
    build_dataset.py    raw JSON to clean tables and quality report
    cli.py              fetch, build, all
  tests/                selection, metrics, build, API
frontend/
  Dockerfile, nginx.conf
  src/
    pages/              Decision, Accuracy, Method
    components/         Kpi, Card, Status
    api.ts              typed client and query hooks
    format.ts           formatters (unit tested)
data/
  raw/                  fetched JSON (not committed)
  processed/            actuals.csv, forecasts.csv.gz, data_quality.json
.github/workflows/ci.yml
```

## API

Read-only `GET` endpoints. Full schema at `/api/docs`. `cutoff` is `HH:MM` UK time on the day before delivery, default `09:00`. `start` and `end` default to the pilot window. Timestamps are UTC. Power is in MW.

| Endpoint | Params | Returns |
| --- | --- | --- |
| `/api/health` | none | Status |
| `/api/meta` | none | Window, default cutoff, last publish, data quality report |
| `/api/forecast` | `delivery_date`, `cutoff` | Half-hourly forecast with publish time, horizon, 80% band, actual, plus day summary |
| `/api/forecast/days` | `cutoff` | One summary row per delivery day |
| `/api/accuracy/summary` | `cutoff`, `start`, `end` | MAE, RMSE, bias, nMAE, P90/P95, shortfall buffer, coverage, band check |
| `/api/accuracy/by-day` | `cutoff`, `start`, `end` | MAE, bias, count per day |
| `/api/accuracy/by-hour` | `cutoff`, `start`, `end` | MAE, bias, count per UK hour |
| `/api/accuracy/by-horizon` | `start`, `end` | MAE, bias, count per 6-hour horizon bucket, all publishes |
| `/api/accuracy/distribution` | `cutoff`, `start`, `end` | Error histogram and error by forecast quartile |

## Method in brief

**Latest forecast at decision time.** For each half-hour of delivery day D, the app uses the WINDFOR row with the latest `publishTime` that is at or before the cutoff on D-1 (default 09:00 UK time). Forecasts published later are never used. If none qualifies, the half-hour is shown as missing.

**Error.** Forecast minus actual, in MW. A positive error means less wind than forecast, so the buyer may be short.

**Metrics.** Bias, MAE, RMSE, nMAE (MAE divided by mean actual), P90 and P95 absolute error, a P90 shortfall buffer (90th percentile of forecast minus actual, floored at 0), and coverage. MAPE is not used because wind can be close to zero.

## Deployment

Deployed as one Vercel project. The React app is served as static files and the FastAPI app runs as a Python function under `/api`. Vercel does not run Docker containers, so it deploys the same code that the Docker setup runs locally.

## Assumptions and limitations

- **Forecast resolution.** WINDFOR forecasts are hourly in the source samples, FUELHH actuals are half-hourly. Each hourly forecast is applied to both half-hours inside that hour. Forecast detail within the hour is therefore flat, which adds some error that is not the forecaster's fault.
- A WINDFOR publish also lists hours already past at publish time. Those are dropped.
- The day-ahead cutoff is user-adjustable. The 09:00 UK default is an assumption, not the exact market gate time.
- The error band is computed over the whole pilot window, so it is in-sample and slightly optimistic.
- WINDFOR and FUELHH may not cover exactly the same wind fleet. Any level gap shows up as bias.
- Demand and prices are out of scope, so the app does not compute the amount to buy, only the wind input to that decision.

## AI usage

AI tools were used in this project. Claude (Anthropic) helped with planning, code scaffolding, tests and documentation. The author reviewed, ran and tested all code, and checked the analysis choices against the brief.

## Data attribution

Contains BMRS data © Elexon Limited copyright and database right 2026. Check the BMRS data licence for the current required wording.
