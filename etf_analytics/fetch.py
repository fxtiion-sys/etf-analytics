"""Download daily ETF prices from Yahoo Finance and cache them as CSV."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

TICKERS = ["XIU.TO", "XIC.TO", "VFV.TO", "SPY", "QQQ", "CAD=X"]
PERIOD = "5y"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "prices.csv"


def download_prices(tickers: list[str] = TICKERS, period: str = PERIOD) -> pd.DataFrame:
    """Download adjusted daily close prices (dividends included) for each ticker."""
    import yfinance as yf  # imported here so cached runs and tests don't need the network

    raw = yf.download(tickers, period=period, auto_adjust=True, progress=False, threads=False)
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no data. Try again later.")

    prices = raw["Close"]
    missing = [t for t in tickers if t not in prices.columns or prices[t].isna().all()]
    if missing:
        raise RuntimeError(f"No price data for: {missing}")
    return prices[tickers]


def load_prices(refresh: bool = False, path: Path = CACHE_PATH) -> pd.DataFrame:
    """Return cached prices if the CSV exists; otherwise download and save them."""
    if path.exists() and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)

    prices = download_prices()
    path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(path)
    return prices


def main() -> None:
    parser = argparse.ArgumentParser(description="Download or load cached ETF prices.")
    parser.add_argument("--refresh", action="store_true", help="re-download even if the CSV exists")
    args = parser.parse_args()

    prices = load_prices(refresh=args.refresh)
    print(f"Rows: {len(prices)}  ({prices.index.min().date()} → {prices.index.max().date()})")
    print("\nMissing values per ticker:")
    print(prices.isna().sum())


if __name__ == "__main__":
    main()