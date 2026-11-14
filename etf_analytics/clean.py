"""Align Canadian and US trading calendars before computing returns."""
from __future__ import annotations

import pandas as pd

from etf_analytics.fetch import load_prices

CANADA = ["XIU.TO", "XIC.TO", "VFV.TO"]
US = ["SPY", "QQQ"]


def align_trading_days(prices: pd.DataFrame) -> pd.DataFrame:
    """Keep only dates where every ticker has a price (both markets open).

    Forward-filling would create fake flat days on holidays and push the
    holiday's move into the next day's return, so those dates are dropped.
    """
    return prices.sort_index().dropna(how="any")


def holiday_mismatches(prices: pd.DataFrame) -> dict[str, pd.DatetimeIndex]:
    """Find dates where only one market (or both) was closed."""
    ca_closed = prices[CANADA].isna().all(axis=1)
    us_closed = prices[US].isna().all(axis=1)
    return {
        "canada_only": prices.index[ca_closed & ~us_closed],
        "us_only": prices.index[us_closed & ~ca_closed],
        "both": prices.index[ca_closed & us_closed],
    }


def main() -> None:
    prices = load_prices()
    aligned = align_trading_days(prices)

    print(f"Rows before: {len(prices)}  after: {len(aligned)}  dropped: {len(prices) - len(aligned)}")
    for name, dates in holiday_mismatches(prices).items():
        examples = ", ".join(d.strftime("%Y-%m-%d") for d in dates[-4:])
        print(f"{name:12s} {len(dates):3d} days   e.g. {examples}")


if __name__ == "__main__":
    main()