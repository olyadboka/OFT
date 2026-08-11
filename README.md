# OFT — Olyad Forex Trading

A self-hosted, hybrid forex trading system: an automated strategy bot plus a
monitoring/control dashboard, trading through the **OANDA v20** API.

> ⚠️ Personal project. Defaults to OANDA's **practice** environment. Do not point
> it at a live/funded account until the risk controls are in place and tested.

## Stack

| Layer           | Tech                                    |
| --------------- | --------------------------------------- |
| Services / bot  | Python 3.12 (asyncio)                   |
| Broker          | OANDA v20 (REST + streaming)            |
| Database        | PostgreSQL + TimescaleDB                |
| Message bus     | Redis Streams                           |
| Dashboard API   | FastAPI + WebSocket                     |
| Frontend        | React + TypeScript + lightweight-charts |
| Package manager | uv                                      |
| Local infra     | Docker Compose                          |

## Architecture (high level)

```
OANDA v20  ──►  Market Data ──►  Redis Streams ──►  Strategy Engine ──►  Execution
   ▲              (candles)                            (signals)         (+ risk gate)
   └────────────────────────── reconciliation ◄──────────────────────────────┘
                                     │
                          PostgreSQL + TimescaleDB
                                     │
                        FastAPI + WebSocket ──►  React dashboard
```

## Build roadmap

Built **broker-first**: the core quant engine runs entirely on a self-contained
`SimBroker` (synthetic prices, fills, accounting) behind a `Broker` interface, so a
real OANDA adapter can drop in later without touching the strategy/risk/backtest code.

- [x] **Step 1** — Repo + local infra (Docker Compose: Postgres/Timescale + Redis)
- [x] **Step 2** — `Broker` interface + Pydantic DTOs + `SimBroker` (sim-first)
- [x] **Step 3** — Strategies (`SMA crossover`, `RSI`, `breakout`) behind a `Strategy` interface
- [x] **Step 4** — Trading engine + backtest runner with metrics (return, drawdown, Sharpe, win-rate)
- [x] **Step 5** — Risk layer (fixed-fractional sizing + drawdown kill-switch) & bracket orders (SL/TP)
- [x] **Step 6** — Parameter sweep optimizer + result persistence (TimescaleDB) + HTTP API + CLI
- [x] **Market data** — TimescaleDB candle store (hypertable) + synthetic ingest + `ReplayBroker` to backtest on stored history (API/CLI wired)
- [ ] **Step 7** — Real OANDA `Broker` adapter (practice account)
- [ ] **Step 8** — React dashboard, harden, observe, go live

## Usage

Everything runs on the in-process `SimBroker` today — no OANDA credentials needed.

```bash
# Run a single backtest and print a metrics report
uv run oft backtest --strategy sma --param fast=10 --param slow=15 --bars 500

# Sweep a parameter grid, ranked by Sharpe
uv run oft sweep --strategy sma --axis fast=5,10,20 --axis slow=15,20,30 --bars 500

# Save a backtest to the database, then list recent stored runs
uv run oft backtest --strategy sma --param fast=10 --param slow=15 --bars 500 --persist
uv run oft results --limit 10

# Ingest synthetic candles into TimescaleDB, then inspect them
uv run oft ingest --instrument EUR_USD --granularity M1 --count 500 --seed 11
uv run oft candles --instrument EUR_USD --limit 20

# Backtest on the *stored* candle history instead of synthetic prices
uv run oft backtest --strategy sma --param fast=5 --param slow=20 \
  --source stored --instrument EUR_USD

# Serve the HTTP API (http://127.0.0.1:8000/docs for the OpenAPI UI)
uv run oft serve
```

> `--persist`, `oft results`, `oft ingest`, `oft candles`, and
> `--source stored` need the Postgres/TimescaleDB container up
> (`docker compose up -d`). Without it they exit with a clear error.
>
> Ingested candles land on canonical bucket boundaries (an `M1` bar at `:00`)
> and upsert by `(instrument, time)`, so re-ingesting the same window is
> idempotent rather than duplicating rows.

Strategies: `sma` (`fast`,`slow`), `rsi` (`window`,`oversold`,`overbought`), `breakout` (`window`).

### HTTP API

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/backtest \
  -H 'content-type: application/json' \
  -d '{"strategy":"sma","params":{"fast":10,"slow":15},"bars":500}'
curl -s -X POST localhost:8000/sweep \
  -H 'content-type: application/json' \
  -d '{"strategy":"sma","grid":{"fast":[5,10],"slow":[15,20]},"bars":300}'

# Persist a backtest (add "persist": true), then query and delete stored runs
curl -s -X POST localhost:8000/backtest \
  -H 'content-type: application/json' \
  -d '{"strategy":"sma","params":{"fast":10,"slow":15},"bars":500,"persist":true}'
curl -s 'localhost:8000/results?limit=10'
curl -s -X DELETE localhost:8000/results/1

# Ingest candles, list them, and backtest on the stored history
curl -s -X POST localhost:8000/candles/ingest \
  -H 'content-type: application/json' \
  -d '{"instrument":"EUR_USD","granularity":"M1","count":500,"seed":11}'
curl -s 'localhost:8000/candles?instrument=EUR_USD&limit=20'
curl -s -X POST localhost:8000/backtest \
  -H 'content-type: application/json' \
  -d '{"strategy":"sma","params":{"fast":5,"slow":20},"source":"stored","instrument":"EUR_USD"}'
```

The persistence and candle endpoints return HTTP 503 when the database is
unreachable; `source":"stored"` returns HTTP 400 if no candles are stored for
the instrument.

### Tests

```bash
uv run pytest        # 107 tests (DB-backed candle/persistence tests skip if Postgres is down)
```

## Local ports

To avoid clashing with other local stacks, this project uses non-default host ports:

| Service    | Host port |
| ---------- | --------- |
| PostgreSQL | 5442      |
| Redis      | 6389      |

## Getting started

Prerequisites: Docker Desktop, Python 3.12, and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Configure environment
cp .env.example .env        # then edit .env with your OANDA practice credentials

# 2. Start local infrastructure (Postgres/TimescaleDB + Redis)
docker compose up -d
docker compose ps           # both services should report "healthy"

# 3. Install Python deps and run
uv run oft
```

Sanity checks:

```bash
# TimescaleDB extension is active
docker exec oft-postgres psql -U oft -d oft -tAc \
  "SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';"

# Redis responds
docker exec oft-redis redis-cli ping   # -> PONG
```
