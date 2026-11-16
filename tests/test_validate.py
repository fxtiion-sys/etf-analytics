"""Tests for the data checks, using small fake data that is clean until we break it on purpose."""

import numpy as np
import pandas as pd
import pytest

from etf_analytics import validate
from etf_analytics.fetch import drop_weekends


def clean_prices(days: int = 30) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-01", periods=days)
    rng = np.random.default_rng(0)
    data = {c: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, days))) for c in validate.REQUIRED_COLUMNS}
    data["CAD=X"] = 1.35 * np.exp(np.cumsum(rng.normal(0, 0.003, days)))
    data["USDCAD"] = data["CAD=X"] * 1.001
    return pd.DataFrame(data, index=idx)


def test_clean_data_passes():
    prices = clean_prices()
    assert validate.check_raw(prices) == []
    assert validate.check_aligned(prices) == []
    validate.validate(prices, prices)  # does not raise


def test_missing_column_is_reported():
    issues = validate.check_raw(clean_prices().drop(columns="SPY"))
    assert issues == ["missing columns: ['SPY']"]


def test_weekend_and_duplicate_dates_are_reported():
    prices = clean_prices()
    saturday = prices.iloc[[-1]].set_axis(pd.to_datetime(["2024-02-10"]))
    issues = validate.check_raw(pd.concat([prices, saturday, saturday]))
    assert any("weekend dates: 2024-02-10" in i for i in issues)
    assert any("duplicate dates" in i for i in issues)


def test_drop_weekends_removes_saturday_row():
    idx = pd.to_datetime(["2026-11-13", "2026-11-14"])  # Friday, Saturday
    prices = pd.DataFrame({"CAD=X": [1.4261, 1.4269]}, index=idx)
    assert list(drop_weekends(prices).index) == [pd.Timestamp("2026-11-13")]


def test_negative_price_is_reported():
    prices = clean_prices()
    prices.iloc[5, 0] = -1.0
    assert any("zero or negative" in i for i in validate.check_raw(prices))


def test_large_jump_is_reported_with_column_and_date():
    prices = clean_prices()
    prices.loc[prices.index[10] :, "QQQ"] *= 1.20  # +20% in one day, then stays there
    issues = validate.check_aligned(prices)
    assert len(issues) == 1
    assert issues[0].startswith("QQQ: daily move of +")
    assert str(prices.index[10].date()) in issues[0]


def test_fx_has_a_tighter_limit_than_etfs():
    prices = clean_prices()
    prices.loc[prices.index[10] :, ["USDCAD", "CAD=X"]] *= 1.06  # +6%: fine for an ETF, not for USD/CAD
    issues = validate.check_aligned(prices)
    assert any(i.startswith("USDCAD: daily move") for i in issues)
    assert any(i.startswith("CAD=X: daily move") for i in issues)


def test_frozen_price_is_reported():
    prices = clean_prices()
    prices.iloc[10:15, prices.columns.get_loc("VFV.TO")] = 150.0  # same value 5 days in a row
    issues = validate.check_aligned(prices)
    assert any(i.startswith("VFV.TO: same value on 5+ days") for i in issues)


def test_long_gap_is_reported():
    prices = clean_prices().drop(pd.bdate_range("2024-01-15", "2024-01-24"))
    issues = validate.check_aligned(prices)
    assert any(i.startswith("gap of") for i in issues)


def test_fx_sources_that_disagree_are_reported():
    prices = clean_prices()
    prices["USDCAD"] = prices["CAD=X"] * 1.05
    issues = validate.check_aligned(prices)
    assert any("differ by more than 3%" in i for i in issues)


def test_validate_lists_every_problem():
    prices = clean_prices().drop(columns="QQQ")
    prices.iloc[5, 0] = 0.0
    with pytest.raises(validate.DataValidationError) as error:
        validate.validate(prices, prices)
    message = str(error.value)
    assert "missing columns" in message and "zero or negative" in message
