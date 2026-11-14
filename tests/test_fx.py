"""Tests for the Bank of Canada USD/CAD rate, using a hand-written Valet response (no network)."""
import numpy as np
import pandas as pd
import pytest

from etf_analytics import fx
from etf_analytics.clean import align_trading_days, missing_fx_days

VALET_SAMPLE = {
    "observations": [
        {"d": "2025-11-10", "FXUSDCAD": {"v": "1.4010"}},
        {"d": "2025-11-12", "FXUSDCAD": {"v": "1.4025"}},
        {"d": "2025-11-07", "FXUSDCAD": {"v": "1.4050"}},
    ]
}


def test_parse_valet_returns_sorted_floats():
    rates = fx.parse_valet(VALET_SAMPLE)
    assert list(rates.index) == list(pd.to_datetime(["2025-11-07", "2025-11-10", "2025-11-12"]))
    assert list(rates) == pytest.approx([1.4050, 1.4010, 1.4025])
    assert rates.name == fx.COLUMN


def test_parse_valet_rejects_empty_response():
    with pytest.raises(RuntimeError):
        fx.parse_valet({"observations": []})


def test_load_usdcad_reads_cache_without_network(tmp_path):
    path = tmp_path / "usdcad.csv"
    fx.parse_valet(VALET_SAMPLE).to_csv(path)
    rates = fx.load_usdcad(start=None, end=None, path=path)  # dates unused when the cache exists
    assert rates.loc["2025-11-10"] == pytest.approx(1.4010)


def test_day_without_rate_is_dropped_when_aligning():
    idx = pd.to_datetime(["2025-11-10", "2025-11-11", "2025-11-12"])  # 11-11: Remembrance Day
    prices = pd.DataFrame({t: [1.0, 2.0, 3.0] for t in ["XIU.TO", "XIC.TO", "VFV.TO", "SPY", "QQQ"]}, index=idx)
    prices = fx.add_usdcad(prices, fx.parse_valet(VALET_SAMPLE))

    assert np.isnan(prices.loc["2025-11-11", fx.COLUMN])
    assert list(missing_fx_days(prices)) == [pd.Timestamp("2025-11-11")]
    assert pd.Timestamp("2025-11-11") not in align_trading_days(prices).index
    