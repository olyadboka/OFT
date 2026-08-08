from fastapi.testclient import TestClient

from oft.api import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "sma" in body["strategies"]


def test_backtest_sma():
    response = client.post(
        "/backtest",
        json={"strategy": "sma", "params": {"fast": 10, "slow": 15}, "bars": 200},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bars"] == 200
    assert "sma-crossover" in body["strategy"]
    assert isinstance(body["sharpe"], float)


def test_backtest_rsi():
    response = client.post(
        "/backtest",
        json={"strategy": "rsi", "params": {"window": 14}, "bars": 200},
    )
    assert response.status_code == 200
    assert "rsi" in response.json()["strategy"]


def test_backtest_unknown_strategy_is_400():
    response = client.post(
        "/backtest", json={"strategy": "nope", "params": {}, "bars": 100}
    )
    assert response.status_code == 400


def test_backtest_invalid_params_is_400():
    response = client.post(
        "/backtest",
        json={"strategy": "sma", "params": {"fast": 20, "slow": 10}, "bars": 100},
    )
    assert response.status_code == 400


def test_sweep_returns_ranked_top():
    response = client.post(
        "/sweep",
        json={
            "strategy": "sma",
            "grid": {"fast": [5, 10], "slow": [15, 20]},
            "bars": 150,
            "top": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4
    assert len(body["top"]) == 3
    sharpes = [row["sharpe"] for row in body["top"]]
    assert sharpes == sorted(sharpes, reverse=True)


def test_sweep_unknown_strategy_is_400():
    response = client.post(
        "/sweep", json={"strategy": "nope", "grid": {"window": [5]}, "bars": 100}
    )
    assert response.status_code == 400
