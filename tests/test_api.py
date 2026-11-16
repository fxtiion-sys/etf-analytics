"""Tests for the REST API, using fake prices or a temporary database instead of data/etf.db."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from etf_analytics import api, charts, fx, metrics, storage
from etf_analytics.clean import align_trading_days
from etf_analytics.fetch import TICKERS


def fake_prices() -> pd.DataFrame:
    """Random walks for every column, with one Canadian holiday (TSX closed, NYSE open)."""
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2024-01-02", periods=300, name="Date")
    columns = [*TICKERS, fx.COLUMN]
    data = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(idx), len(columns))), axis=0))
    prices = pd.DataFrame(data, index=idx, columns=columns)
    prices.loc["2024-02-19", ["XIU.TO", "XIC.TO", "VFV.TO"]] = np.nan  # Family Day
    return prices


@pytest.fixture
def client():
    prices = fake_prices()
    api.app.dependency_overrides[api.get_prices] = lambda: prices
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_etf_list_matches_the_report():
    assert [ticker for ticker, _, _ in api.ETFS.values()] == charts.ETFS


def test_list_etfs(client):
    response = client.get("/etfs")

    assert response.status_code == 200
    etfs = response.json()
    assert [e["symbol"] for e in etfs] == ["VFV", "SPY", "XIU", "XIC", "QQQ"]
    assert etfs[0] == {
        "symbol": "VFV",
        "ticker": "VFV.TO",
        "index": "S&P 500",
        "currency": "CAD",
        "first_date": "2024-01-02",
        "last_date": "2025-02-24",
    }


def test_metrics_match_the_summary_table(client):
    response = client.get("/etfs/VFV/metrics")

    assert response.status_code == 200
    body = response.json()
    aligned = align_trading_days(fake_prices())
    expected = metrics.summary_table(aligned[charts.ETFS], market="SPY").loc["VFV.TO"]
    assert body["symbol"] == "VFV"
    assert body["trading_days"] == 299  # the holiday is dropped
    assert body["annual_return"] == pytest.approx(expected["annual_return"])
    assert body["max_drawdown"] == pytest.approx(expected["max_drawdown"])
    assert body["beta_vs_spy"] == pytest.approx(expected["beta_vs_SPY"])


def test_spy_has_a_beta_of_one_against_itself(client):
    assert client.get("/etfs/SPY/metrics").json()["beta_vs_spy"] == pytest.approx(1.0)


def test_symbol_is_case_insensitive(client):
    assert client.get("/etfs/vfv/metrics").json()["symbol"] == "VFV"


def test_unknown_symbol_returns_404(client):
    response = client.get("/etfs/ABC/metrics")

    assert response.status_code == 404
    assert "Available: VFV, SPY, XIU, XIC, QQQ" in response.json()["detail"]


def test_prices_between_two_dates(client):
    response = client.get("/etfs/VFV/prices", params={"start": "2024-02-15", "end": "2024-02-21"})

    assert response.status_code == 200
    days = [p["date"] for p in response.json()]
    assert days == ["2024-02-15", "2024-02-16", "2024-02-20", "2024-02-21"]  # no row on the holiday


def test_us_etf_still_has_a_price_on_a_canadian_holiday(client):
    response = client.get("/etfs/SPY/prices", params={"start": "2024-02-19", "end": "2024-02-19"})

    assert [p["date"] for p in response.json()] == ["2024-02-19"]


def test_start_after_end_returns_400(client):
    response = client.get("/etfs/VFV/prices", params={"start": "2024-03-01", "end": "2024-02-01"})

    assert response.status_code == 400


def test_invalid_date_returns_422(client):
    assert client.get("/etfs/VFV/prices", params={"start": "not-a-date"}).status_code == 422


def test_empty_database_returns_503_without_downloading(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "etf.db")

    response = TestClient(api.app).get("/etfs")

    assert response.status_code == 503
    assert "fetch" in response.json()["detail"]


def test_reads_from_the_database(tmp_path, monkeypatch):
    path = tmp_path / "etf.db"
    prices = fake_prices()
    conn = storage.connect(path)
    storage.upsert(conn, prices[TICKERS], "yahoo")
    storage.upsert(conn, prices[[fx.COLUMN]], "boc")
    conn.close()
    monkeypatch.setattr(storage, "DB_PATH", path)

    response = TestClient(api.app).get("/etfs/QQQ/prices", params={"end": "2024-01-03"})

    assert response.status_code == 200
    assert [p["close"] for p in response.json()] == pytest.approx(prices["QQQ"].iloc[:2].tolist())
