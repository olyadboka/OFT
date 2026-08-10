
"""Command-line interface: run backtests, sweeps, or the HTTP server."""

from __future__ import annotations

import argparse
import asyncio

from oft.backtest import Backtester, by_return, by_sharpe, sweep
from oft.broker import SimBroker
from oft.persistence import ResultStore
from oft.risk import FixedFractionalRisk
from oft.strategy import STRATEGIES, make_strategy


def _coerce(text: str):
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            continue
    return text


def _parse_params(pairs: list[str]) -> dict:
    params = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        params[key] = _coerce(value)
    return params


def _parse_grid(axes: list[str]) -> dict:
    grid = {}
    for axis in axes:
        key, _, values = axis.partition("=")
        grid[key] = [_coerce(v) for v in values.split(",") if v]
    return grid


def _cmd_backtest(args) -> int:
    try:
        strategy = make_strategy(args.strategy, _parse_params(args.param))
    except (TypeError, ValueError) as exc:
        print(f"error: {exc}")
        return 2
    broker = SimBroker(seed=args.seed, tick_seconds=0,
                       volatility=args.volatility)
    risk = FixedFractionalRisk(risk_per_trade=args.risk)
    backtester = Backtester(broker, strategy, "EUR_USD", risk=risk)
    result = asyncio.run(backtester.run(args.bars))
    print(f"strategy        {strategy.name}")
    print(result.report())
    if args.persist:
        try:
            result_id = asyncio.run(
                _persist(strategy.name, _parse_params(args.param), result)
            )
        except Exception as exc:  # noqa: BLE001 - report, don't crash the report
            print(f"persist failed  {exc}")
            return 1
        print(f"saved           id={result_id}")
    return 0


async def _persist(strategy: str, params: dict, result) -> int:
    store = ResultStore()
    await store.init_schema()
    return await store.save(strategy, params, result)


def _cmd_results(args) -> int:
    try:
        rows = asyncio.run(ResultStore().recent(limit=args.limit))
    except Exception as exc:  # noqa: BLE001 - db down => clear message, non-zero exit
        print(f"error: {exc}")
        return 1
    if not rows:
        print("no stored results")
        return 0
    for row in rows:
        print(
            f"{row.id:>6}  {row.strategy:<24}  "
            f"return={float(row.total_return):+.2%}  sharpe={row.sharpe:+.4f}"
        )
    return 0


def _cmd_sweep(args) -> int:
    if args.strategy not in STRATEGIES:
        print(f"error: unknown strategy: {args.strategy!r}")
        return 2
    grid = _parse_grid(args.axis) or {
        "fast": [5, 10, 20], "slow": [15, 20, 30]}

    def build(params: dict) -> Backtester:
        broker = SimBroker(seed=args.seed, tick_seconds=0,
                           volatility=args.volatility)
        return Backtester(
            broker, make_strategy(args.strategy, params), "EUR_USD",
            risk=FixedFractionalRisk(),
        )

    objective = by_return if args.objective == "return" else by_sharpe
    trials = asyncio.run(sweep(build, grid, args.bars, objective=objective))
    print(f"combos ranked: {len(trials)}")
    for trial in trials[: args.top]:
        result = trial.result
        print(
            f"{trial.params}  return={float(result.total_return):+.2%}  "
            f"sharpe={result.sharpe:+.4f}  trades={result.trades}"
        )
    return 0


def _cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run("oft.api:app", host=args.host, port=args.port)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oft")
    sub = parser.add_subparsers(dest="command", required=True)

    backtest = sub.add_parser("backtest", help="run a single backtest")
    backtest.add_argument("--strategy", default="sma")
    backtest.add_argument("--param", action="append",
                          default=[], metavar="KEY=VALUE")
    backtest.add_argument("--bars", type=int, default=500)
    backtest.add_argument("--seed", type=int, default=11)
    backtest.add_argument("--volatility", type=float, default=0.001)
    backtest.add_argument("--risk", default="0.01")
    backtest.add_argument("--persist", action="store_true",
                          help="save result to the database")
    backtest.set_defaults(func=_cmd_backtest)

    swept = sub.add_parser("sweep", help="sweep a parameter grid")
    swept.add_argument("--strategy", default="sma")
    swept.add_argument("--axis", action="append",
                       default=[], metavar="KEY=V1,V2")
    swept.add_argument("--bars", type=int, default=500)
    swept.add_argument("--seed", type=int, default=11)
    swept.add_argument("--volatility", type=float, default=0.001)
    swept.add_argument("--objective", default="sharpe")
    swept.add_argument("--top", type=int, default=5)
    swept.set_defaults(func=_cmd_sweep)

    serve = sub.add_parser("serve", help="run the HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=_cmd_serve)

    results = sub.add_parser(
        "results", help="list recent stored backtest results")
    results.add_argument("--limit", type=int, default=10)
    results.set_defaults(func=_cmd_results)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)
