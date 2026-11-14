"""VFV vs SPY: convert SPY to Canadian dollars and measure how closely VFV tracks it."""
from __future__ import annotations

import numpy as np
import pandas as pd

from etf_analytics import metrics
from etf_analytics.clean import align_trading_days
from etf_analytics.fetch import load_prices


def to_cad(usd_prices: pd.Series, usdcad: pd.Series) -> pd.Series:
    """USD price x USD/CAD rate (CAD per 1 USD) = price in Canadian dollars."""
    return usd_prices * usdcad


def calendar_year_returns(prices: pd.Series) -> pd.Series:
    """Return for each calendar year, from the previous year's last close to this year's last close.

    The first (partial) year has no starting point, so it is dropped.
    The latest year is year-to-date.
    """
    year_end = prices.groupby(prices.index.year).last()
    return year_end.pct_change().iloc[1:]


def tracking_difference(etf_prices: pd.Series, benchmark_prices: pd.Series) -> pd.Series:
    """Yearly ETF return minus benchmark return. Negative means the ETF lagged."""
    return calendar_year_returns(etf_prices) - calendar_year_returns(benchmark_prices)


def rolling_tracking_error(
        etf_returns: pd.Series, benchmark_returns: pd.Series, window: int = 60, periods: int = 252
) -> pd.Series:
    """Annualized rolling standard deviation of daily return differences."""
    return (etf_returns - benchmark_returns).rolling(window).std() * np.sqrt(periods)


def main() -> None:
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    prices = align_trading_days(load_prices())
    spy_cad = to_cad(prices["SPY"], prices["CAD=X"]).rename("SPY_CAD")
    compare = pd.concat([prices["VFV.TO"], spy_cad, prices["SPY"]], axis=1)

    print("== Headline metrics ==")
    print(metrics.summary_table(compare, market="SPY_CAD").round(3))

    yearly = pd.DataFrame({
        "VFV": calendar_year_returns(prices["VFV.TO"]),
        "SPY_CAD": calendar_year_returns(spy_cad),
    })
    yearly["difference"] = yearly["VFV"] - yearly["SPY_CAD"]
    print("\n== Calendar-year returns (last year is year-to-date) ==")
    print(yearly.round(4))

    returns = metrics.daily_returns(compare)
    rolling_te = rolling_tracking_error(returns["VFV.TO"], returns["SPY_CAD"])
    full_te = (returns["VFV.TO"] - returns["SPY_CAD"]).std() * np.sqrt(252)
    print(f"\nTracking error (full period, annualized): {full_te:.3%}")
    print(f"60-day rolling tracking error: median {rolling_te.median():.3%}, max {rolling_te.max():.3%}")

    fx = prices["CAD=X"]
    fx_returns = metrics.daily_returns(fx)
    print(f"\nUSD/CAD: {fx.iloc[0]:.4f} -> {fx.iloc[-1]:.4f} ({fx.iloc[-1] / fx.iloc[0] - 1:+.1%})")
    print(f"Correlation of SPY (USD) daily returns with USD/CAD: {returns['SPY'].corr(fx_returns):.2f}")


if __name__ == "__main__":
    main()