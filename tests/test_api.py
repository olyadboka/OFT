import pytest
from fastapi.testclient import TestClient

from oft.api import app
from oft.persistence import ResultStore

client = TestClient(app)


def _require_db():
    """Skip a test unless a database is reachable (mirrors test_persistence)."""
    import asyncio

    async def _check():
        await ResultStore().init_schema()

    try:
        asyncio.run(_check())
    except Exception as exc:  # noqa: BLE001 - any connection failure => skip
        pytest.skip(f"database not available: {exc}")


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


def test_backtest_without_persist_has_no_id():
    response = client.post(
        "/backtest",
        json={"strategy": "sma", "params": {"fast": 10, "slow": 15}, "bars": 100},
    )
    assert response.status_code == 200
    assert response.json()["id"] is None


def test_persist_then_list_then_delete():
    _require_db()
    response = client.post(
        "/backtest",
        json={
            "strategy": "sma",
            "params": {"fast": 10, "slow": 15},
            "bars": 150,
            "persist": True,
        },
    )
    assert response.status_code == 200
    result_id = response.json()["id"]
    assert isinstance(result_id, int)

    try:
        listed = client.get("/results", params={"limit": 50})
        assert listed.status_code == 200
        rows = listed.json()
        row = next(r for r in rows if r["id"] == result_id)
        assert "sma-crossover" in row["strategy"]
        assert row["params"] == {"fast": 10, "slow": 15}
        assert row["bars"] == 150
    finally:
        deleted = client.delete(f"/results/{result_id}")
        assert deleted.status_code == 204

    after = client.get("/results", params={"limit": 50}).json()
    assert all(r["id"] != result_id for r in after)
