"""Tests for the Markdown report, using small fake data (no network)."""
import numpy as np
import pandas as pd

from etf_analytics import charts, report


def fake_prices():
    idx = pd.bdate_range("2021-12-01", "2023-03-01")
    rng = np.random.default_rng(0)
    data = {t: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))) for t in charts.ETFS}
    data["CAD=X"] = 1.3 * np.exp(np.cumsum(rng.normal(0, 0.003, len(idx))))
    data["USDCAD"] = data["CAD=X"] * (1 + rng.normal(0, 0.001, len(idx)))
    prices = pd.DataFrame(data, index=idx)
    prices.loc["2022-07-01", ["XIU.TO", "XIC.TO", "VFV.TO"]] = np.nan  # Canada Day
    prices.loc["2022-07-04", ["SPY", "QQQ"]] = np.nan                  # US Independence Day
    prices.loc["2022-11-11", "USDCAD"] = np.nan                       # Remembrance Day (Bank of Canada closed)
    return prices


def test_markdown_table_formats_values():
    df = pd.DataFrame({"Return": [0.1234]}, index=["VFV"])
    assert report.markdown_table(df, {"Return": "{:.1%}"}, "ETF") == (
        "| ETF | Return |\n|---|---:|\n| VFV | 12.3% |"
    )


def test_build_report_writes_markdown_and_charts(tmp_path):
    path = report.build_report(fake_prices(), out_dir=tmp_path)

    text = path.read_text()
    assert text.startswith("# ETF Analytics Report")
    assert "Closed in Canada only: 1 days" in text
    assert "no Bank of Canada rate: 1 days" in text
    for chart in ["cumulative_returns.png", "vfv_vs_spy.png", "tracking_difference.png"]:
        assert f"({chart})" in text
        assert (tmp_path / chart).exists()