"""Unit tests for metrics, using tiny series whose answers can be worked out by hand."""
import numpy as np
import pandas as pd
import pytest

from etf_analytics import metrics


def series(values, start="2021-01-01"):
    """Daily series with a date index, like real price data."""
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"), dtype=float)


def test_daily_returns_up_then_down():
    # 100 -> 110 is +10%, 110 -> 99 is -10%
    result = metrics.daily_returns(series([100, 110, 99]))
    assert list(result) == pytest.approx([0.10, -0.10])


def test_drawdown_series():
    # Peak 110, falls to 99 (-10%), then a new high at 120 resets to 0
    result = metrics.drawdown(series([100, 110, 99, 120]))
    assert list(result) == pytest.approx([0.0, 0.0, -0.10, 0.0])


def test_max_drawdown_is_worst_fall_from_peak():
    assert metrics.max_drawdown(series([100, 110, 99])) == pytest.approx(-0.10)


def test_max_drawdown_is_zero_when_price_only_rises():
    assert metrics.max_drawdown(series([100, 101, 102, 103])) == 0.0


def test_annualized_return_doubling_over_four_years():
    # 2021-01-01 -> 2025-01-01 is 1461 days = exactly 4 * 365.25
    prices = pd.Series([100.0, 200.0], index=pd.to_datetime(["2021-01-01", "2025-01-01"]))
    assert metrics.annualized_return(prices) == pytest.approx(2 ** (1 / 4) - 1)


def test_volatility_is_zero_for_constant_returns():
    assert metrics.annualized_volatility(series([0.01, 0.01, 0.01])) == pytest.approx(0.0)


def test_sharpe_ratio_by_hand():
    # mean = 0.02, sample std = 0.01 * sqrt(2), so daily ratio = sqrt(2); annualized = sqrt(2 * 252)
    returns = series([0.01, 0.03])
    assert metrics.sharpe_ratio(returns) == pytest.approx(np.sqrt(2 * 252))


def test_beta_of_market_with_itself_is_one():
    market = series([0.01, -0.02, 0.03, 0.005])
    assert metrics.beta(market, market) == pytest.approx(1.0)


def test_beta_of_leveraged_asset_is_two():
    market = series([0.01, -0.02, 0.03, 0.005])
    assert metrics.beta(market * 2, market) == pytest.approx(2.0)


def test_correlation_of_opposite_series_is_minus_one():
    a = series([0.01, -0.02, 0.03, 0.005])
    corr = metrics.correlation_matrix(pd.DataFrame({"a": a, "b": -a}))
    assert corr.loc["a", "b"] == pytest.approx(-1.0)