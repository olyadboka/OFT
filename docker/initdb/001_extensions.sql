-- Runs exactly once, when the Postgres data volume is first initialized.
-- Enables the TimescaleDB extension so we can turn candle/tick tables into
-- hypertables (auto-partitioned, fast time-range queries) in later migrations.
CREATE EXTENSION IF NOT EXISTS timescaledb;
