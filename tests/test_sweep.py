from oft.backtest import Backtester, by_return, expand_grid, sweep
from oft.broker import SimBroker
from oft.strategy import SmaCrossover


def _build(params):
    broker = SimBroker(seed=7, tick_seconds=0, volatility=0.001)
    return Backtester(
        broker, SmaCrossover(params["fast"], params["slow"]), "EUR_USD", units="1000"
    )


def test_expand_grid_is_cartesian_product():
    combos = expand_grid({"a": [1, 2], "b": [3, 4, 5]})
    assert len(combos) == 6
    assert {"a": 1, "b": 3} in combos
    assert {"a": 2, "b": 5} in combos


def test_expand_grid_single_axis():
    combos = expand_grid({"fast": [3, 5, 10]})
    assert combos == [{"fast": 3}, {"fast": 5}, {"fast": 10}]


async def test_sweep_returns_a_trial_per_valid_combo():
    grid = {"fast": [3, 5], "slow": [15, 20]}
    trials = await sweep(_build, grid, bars=200)
    assert len(trials) == 4
    for trial in trials:
        assert "fast" in trial.params
        assert trial.result.bars == 200


async def test_sweep_ranks_best_first():
    grid = {"fast": [3, 5, 10], "slow": [15, 20]}
    trials = await sweep(_build, grid, bars=200, objective=by_return)
    values = [by_return(trial.result) for trial in trials]
    assert values == sorted(values, reverse=True)


async def test_sweep_skips_invalid_combinations():
    grid = {"fast": [5, 20], "slow": [10, 20]}
    trials = await sweep(_build, grid, bars=50)
    assert len(trials) == 2


async def test_sweep_is_deterministic():
    grid = {"fast": [3, 5], "slow": [15, 20]}
    first = await sweep(_build, grid, bars=150)
    second = await sweep(_build, grid, bars=150)
    assert [t.params for t in first] == [t.params for t in second]
    assert [t.result for t in first] == [t.result for t in second]
