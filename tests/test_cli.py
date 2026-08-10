import asyncio

import pytest

from oft.cli import _parse_grid, _parse_params, main
from oft.persistence import ResultStore


def _require_db():
    """Skip a test unless a database is reachable (mirrors test_persistence)."""
    try:
        asyncio.run(ResultStore().init_schema())
    except Exception as exc:  # noqa: BLE001 - any connection failure => skip
        pytest.skip(f"database not available: {exc}")


def test_parse_params_coerces_types():
    params = _parse_params(["fast=10", "risk=0.01", "name=x"])
    assert params == {"fast": 10, "risk": 0.01, "name": "x"}


def test_parse_grid_splits_axes():
    grid = _parse_grid(["fast=5,10", "slow=15,20"])
    assert grid == {"fast": [5, 10], "slow": [15, 20]}


def test_backtest_command_prints_report(capsys):
    code = main(
        ["backtest", "--strategy", "sma", "--param", "fast=10", "--param", "slow=15",
         "--bars", "150"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "sma-crossover" in out
    assert "total return" in out


def test_backtest_unknown_strategy_returns_error(capsys):
    code = main(["backtest", "--strategy", "nope", "--bars", "50"])
    assert code == 2
    assert "error" in capsys.readouterr().out


def test_backtest_invalid_params_returns_error(capsys):
    code = main(
        ["backtest", "--strategy", "sma", "--param", "fast=20", "--param", "slow=10",
         "--bars", "50"]
    )
    assert code == 2


def test_sweep_command_prints_ranking(capsys):
    code = main(
        ["sweep", "--strategy", "sma", "--axis", "fast=5,10", "--axis", "slow=15,20",
         "--bars", "120"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "combos ranked: 4" in out


def test_backtest_persist_then_results(capsys):
    _require_db()
    code = main(
        ["backtest", "--strategy", "sma", "--param", "fast=10", "--param", "slow=15",
         "--bars", "150", "--persist"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "saved           id=" in out
    result_id = int(out.split("id=")[1].split()[0])

    try:
        code = main(["results", "--limit", "50"])
        assert code == 0
        listing = capsys.readouterr().out
        assert str(result_id) in listing
        assert "sma-crossover" in listing
    finally:
        asyncio.run(ResultStore().delete(result_id))
