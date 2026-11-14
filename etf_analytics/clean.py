"""Align Canadian and US trading calendars before computing returns."""
from __future__ import annotations

import pandas as pd

from etf_analytics.fetch import fx
from etf_analytics.fetch import load_data

CANADA = ["XIU.TO", "XIC.TO", "VFV.TO"]
US = ["SPY", "QQQ"]


def align_trading_days(prices: pd.DataFrame) -> pd.DataFrame:
    """Keep only dates where every column has a value (both markets and the Bank of Canada open).

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

def missing_fx_days(prices: pd.DataFrame) -> pd.DatetimeIndex:
    """Dates when both markets were open but the Bank of Canada published no rate.

    The Bank is closed on some federal holidays when the TSX trades,
    such as Remembrance Day and the National Day for Truth and Reconciliation.
    """
    if fx.COLUMN not in prices.columns:
        return pd.DatetimeIndex([])
    markets_open = prices[CANADA + US].notna().all(axis=1)
    return prices.index[markets_open & prices[fx.COLUMN].isna()]


def main() -> None:
    prices = load_data()
    aligned = align_trading_days(prices)

    print(f"Rows before: {len(prices)}  after: {len(aligned)}  dropped: {len(prices) - len(aligned)}")
    for name, dates in holiday_mismatches(prices).items():
        examples = ", ".join(d.strftime("%Y-%m-%d") for d in dates[-4:])
        print(f"{name:12s} {len(dates):3d} days   e.g. {examples}")
        no_fx = missing_fx_days(prices)
        print(f"{'no BoC rate':12s} {len(no_fx):3d} days   e.g. {', '.join(d.strftime('%Y-%m-%d') for d in no_fx[-4:])}")


if __name__ == "__main__":
    main()