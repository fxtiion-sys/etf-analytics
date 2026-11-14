"""Unit tests for the VFV vs SPY tracking functions."""
import pandas as pd
import pytest

from etf_analytics import tracking


def test_to_cad_multiplies_by_exchange_rate():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    usd = pd.Series([10.0, 20.0], index=idx)
    usdcad = pd.Series([1.3, 1.4], index=idx)
    assert list(tracking.to_cad(usd, usdcad)) == pytest.approx([13.0, 28.0])


def test_calendar_year_returns_uses_previous_year_end():
    prices = pd.Series(
        [100.0, 105.0, 110.0, 99.0],
        index=pd.to_datetime(["2021-12-31", "2022-06-30", "2022-12-30", "2023-12-29"]),
    )
    result = tracking.calendar_year_returns(prices)
    assert list(result.index) == [2022, 2023]
    assert list(result) == pytest.approx([0.10, -0.10])


def test_tracking_difference_is_negative_when_etf_lags():
    idx = pd.to_datetime(["2021-12-31", "2022-12-30"])
    benchmark = pd.Series([100.0, 110.0], index=idx)  # +10%
    etf = pd.Series([100.0, 109.0], index=idx)        # +9%
    assert tracking.tracking_difference(etf, benchmark).iloc[0] == pytest.approx(-0.01)


def test_tracking_error_is_zero_for_identical_returns():
    returns = pd.Series([0.01, -0.02, 0.03, 0.005], index=pd.date_range("2024-01-01", periods=4))
    result = tracking.rolling_tracking_error(returns, returns, window=3).dropna()
    assert (result == 0).all()