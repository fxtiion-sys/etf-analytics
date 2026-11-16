"""Download daily ETF prices and the USD/CAD rate, and keep the SQLite database up to date."""

from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Callable
from datetime import date, timedelta

import numpy as np
import pandas as pd

from etf_analytics import fx, storage

TICKERS = ["XIU.TO", "XIC.TO", "VFV.TO", "SPY", "QQQ", "CAD=X"]
START_DATE = date(2021, 11, 15)  # first day of the analysis
OVERLAP_DAYS = 10  # re-download the last 10 days each update, to catch late corrections

PriceDownloader = Callable[[date, date], pd.DataFrame]
RateDownloader = Callable[[date, date], pd.Series]


def download_prices(start: date, end: date) -> pd.DataFrame:
    """Download adjusted daily close prices (dividends included) from start to end, inclusive."""
    import yfinance as yf  # imported here so tests don't need the network

    # yfinance treats `end` as exclusive, so ask for one more day.
    raw = yf.download(
        TICKERS, start=start, end=end + timedelta(days=1), auto_adjust=True, progress=False, threads=False
    )
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no data. Try again later.")

    prices = raw["Close"]
    missing = [t for t in TICKERS if t not in prices.columns or prices[t].isna().all()]
    if missing:
        raise RuntimeError(f"No price data for: {missing}")
    return prices[TICKERS]


def drop_weekends(prices: pd.DataFrame) -> pd.DataFrame:
    """Remove Saturday and Sunday rows."""
    return prices[prices.index.day_of_week < 5]


def history_changed(stored: pd.DataFrame, fresh: pd.DataFrame, before: pd.Timestamp) -> bool:
    """True if Yahoo's adjusted prices before a date differ from what is stored.

    Adjusted prices are rescaled back through history every time a fund pays a dividend.
    Appending new days to old, differently scaled values would hide that dividend,
    so a change in the overlapping days means the whole history must be reloaded.
    """
    days = stored.index[stored.index < before].intersection(fresh.index)
    columns = stored.columns.intersection(fresh.columns)
    old = stored.loc[days, columns].to_numpy(dtype=float)
    new = fresh.loc[days, columns].to_numpy(dtype=float)
    return not np.allclose(old, new, rtol=1e-4, equal_nan=True)


def update_prices(conn: sqlite3.Connection, today: date, download: PriceDownloader = download_prices) -> str:
    """Bring Yahoo prices up to date. Returns a short description of what was done."""
    last = storage.last_date(conn, "yahoo")
    if last is not None:
        start = (last - pd.Timedelta(days=OVERLAP_DAYS)).date()
        fresh = drop_weekends(download(start, today))
        stored = storage.read_wide(conn, source="yahoo")
        if not history_changed(stored, fresh, before=last):
            rows = storage.upsert(conn, fresh, "yahoo")
            return f"Yahoo: incremental update from {start}, {rows:,} rows written"

    storage.delete_source(conn, "yahoo")
    rows = storage.upsert(conn, drop_weekends(download(START_DATE, today)), "yahoo")
    reason = "empty database" if last is None else "adjusted history changed"
    return f"Yahoo: full reload ({reason}), {rows:,} rows written"


def update_usdcad(conn: sqlite3.Connection, today: date, download: RateDownloader = fx.download_usdcad) -> str:
    """Bring the Bank of Canada USD/CAD rate up to date."""
    last = storage.last_date(conn, "boc")
    start = START_DATE if last is None else (last - pd.Timedelta(days=OVERLAP_DAYS)).date()
    rows = storage.upsert(conn, download(start, today).to_frame(fx.COLUMN), "boc")
    return f"Bank of Canada: from {start}, {rows:,} rows written"


def load_data(conn: sqlite3.Connection | None = None) -> pd.DataFrame:
    """Yahoo prices plus the Bank of Canada USD/CAD rate from the database.

    If the database is empty, everything is downloaded first.
    - Data stops at the latest date both sources have published. The Bank of Canada
      publishes at 4:30 p.m. ET, so today's row is left out until its rate exists,
      instead of being mistaken for a Bank of Canada holiday.
    - Weekend rows are removed: Yahoo's currency feed can include a Saturday with only
      CAD=X, which would otherwise be counted as a day when both markets were closed.
    """
    conn = conn or storage.connect()
    last_yahoo, last_boc = storage.last_date(conn, "yahoo"), storage.last_date(conn, "boc")
    if last_yahoo is None or last_boc is None:
        update_prices(conn, date.today())
        update_usdcad(conn, date.today())
        last_yahoo, last_boc = storage.last_date(conn, "yahoo"), storage.last_date(conn, "boc")
    if last_yahoo is None or last_boc is None:
        raise RuntimeError("The database is still empty after downloading.")

    data = storage.read_wide(conn).loc[: min(last_yahoo, last_boc)]
    return drop_weekends(data.reindex(columns=[*TICKERS, fx.COLUMN]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Update the price database with the latest data.")
    parser.add_argument("--full", action="store_true", help="delete stored data and download everything again")
    args = parser.parse_args()

    conn = storage.connect()
    if args.full:
        storage.delete_source(conn, "yahoo")
        storage.delete_source(conn, "boc")
    print(update_prices(conn, date.today()))
    print(update_usdcad(conn, date.today()))

    prices = load_data(conn)
    print(f"Rows: {len(prices):,}  ({prices.index.min().date()} → {prices.index.max().date()})")


if __name__ == "__main__":
    main()
