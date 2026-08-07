# OFT — Olya Forex Trading

A self-hosted, hybrid forex trading system: an automated strategy bot plus a
monitoring/control dashboard, trading through the **OANDA v20** API.

> ⚠️ Personal project. Defaults to OANDA's **practice** environment. Do not point
> it at a live/funded account until the risk controls are in place and tested.

## Stack

| Layer            | Tech                                   |
| ---------------- | -------------------------------------- |
| Services / bot   | Python 3.12 (asyncio)                  |
| Broker           | OANDA v20 (REST + streaming)           |
| Database         | PostgreSQL + TimescaleDB               |
| Message bus      | Redis Streams                          |
| Dashboard API    | FastAPI + WebSocket                    |
| Frontend         | React + TypeScript + lightweight-charts|
| Package manager  | uv                                     |
| Local infra      | Docker Compose                         |

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

- [x] **Step 1** — Repo + local infra (Docker Compose: Postgres/Timescale + Redis)
- [ ] **Step 2** — OANDA async client wrapper
- [ ] **Step 3** — Market-data service (stream + store candles)
- [ ] **Step 4** — Strategy interface + backtest engine
- [ ] **Step 5** — Risk gate + execution service (practice account)
- [ ] **Step 6** — Strategy engine as a service
- [ ] **Step 7** — Dashboard (FastAPI + React)
- [ ] **Step 8** — Harden, observe, go live

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
