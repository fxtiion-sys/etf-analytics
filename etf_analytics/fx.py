"""Download the official USD/CAD rate from the Bank of Canada Valet API and cache it as CSV."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

SERIES = "FXUSDCAD"  # Canadian dollars per 1 US dollar, Bank of Canada daily average
COLUMN = "USDCAD"    # column name used in the price table
VALET_URL = "https://www.bankofcanada.ca/valet/observations/{series}/json?start_date={start}&end_date={end}"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "usdcad_boc.csv"


def parse_valet(payload: dict, series: str = SERIES) -> pd.Series:
    """Turn a Valet JSON response into a date-indexed Series of floats."""
    rows = {
        pd.Timestamp(obs["d"]): float(obs[series]["v"])
        for obs in payload["observations"]
        if obs.get(series, {}).get("v") not in (None, "")
    }
    if not rows:
        raise RuntimeError(f"Bank of Canada returned no observations for {series}.")
    rates = pd.Series(rows, name=COLUMN).sort_index()
    rates.index.name = "Date"
    return rates


def download_usdcad(start: date, end: date) -> pd.Series:
    """Download the Bank of Canada USD/CAD rate between two dates (inclusive)."""
    import requests  # installed with yfinance; imported here so tests don't need the network

    url = VALET_URL.format(series=SERIES, start=start.isoformat(), end=end.isoformat())
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return parse_valet(response.json())


def load_usdcad(start: date, end: date, refresh: bool = False, path: Path = CACHE_PATH) -> pd.Series:
    """Return cached rates if the CSV exists; otherwise download and save them."""
    if path.exists() and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)[COLUMN]

    rates = download_usdcad(start, end)
    path.parent.mkdir(parents=True, exist_ok=True)
    rates.to_csv(path)
    return rates


def add_usdcad(prices: pd.DataFrame, rates: pd.Series) -> pd.DataFrame:
    """Add the Bank of Canada rate as a column. Days without a rate stay empty (NaN)."""
    return prices.join(rates.rename(COLUMN), how="left")