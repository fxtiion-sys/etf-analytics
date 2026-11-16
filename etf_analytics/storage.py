"""Store daily prices and exchange rates in a SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "etf.db"

# One row per (date, symbol). Long format: adding a ticker needs no schema change.
SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    date   TEXT NOT NULL,  -- YYYY-MM-DD
    symbol TEXT NOT NULL,  -- Yahoo ticker, or USDCAD for the Bank of Canada rate
    value  REAL NOT NULL CHECK (value > 0),
    source TEXT NOT NULL,  -- 'yahoo' or 'boc'
    PRIMARY KEY (date, symbol)
)
"""


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open the database, creating the file and the table if needed."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA)
    return conn


def upsert(conn: sqlite3.Connection, wide: pd.DataFrame, source: str) -> int:
    """Insert or replace values from a date x symbol table. Empty cells are skipped.

    Returns the number of rows written.
    """
    long = wide.rename_axis(index="date", columns="symbol").stack().dropna()
    rows = [(day.strftime("%Y-%m-%d"), symbol, float(value), source) for (day, symbol), value in long.items()]
    with conn:  # one transaction: either every row is written or none
        conn.executemany(
            """
            INSERT INTO prices (date, symbol, value, source) VALUES (?, ?, ?, ?)
                ON CONFLICT (date, symbol) DO UPDATE SET value = excluded.value, source = excluded.source
            """,
            rows,
        )
    return len(rows)


def read_wide(conn: sqlite3.Connection, source: str | None = None) -> pd.DataFrame:
    """Read stored values back as a date x symbol table (missing values become NaN)."""
    query = "SELECT date, symbol, value FROM prices"
    params: tuple[str, ...] = ()
    if source is not None:
        query += " WHERE source = ?"
        params = (source,)
    long = pd.read_sql_query(query, conn, params=params, parse_dates=["date"])
    wide = long.pivot(index="date", columns="symbol", values="value").sort_index()
    wide.index.name = "Date"
    wide.columns.name = None
    return wide


def last_date(conn: sqlite3.Connection, source: str) -> pd.Timestamp | None:
    """Latest date stored for a source, or None if there is nothing yet."""
    (value,) = conn.execute("SELECT MAX(date) FROM prices WHERE source = ?", (source,)).fetchone()
    return None if value is None else pd.Timestamp(value)


def delete_source(conn: sqlite3.Connection, source: str) -> None:
    """Remove every row from one source, before a full reload."""
    with conn:
        conn.execute("DELETE FROM prices WHERE source = ?", (source,))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the old CSV caches into the SQLite database.")
    parser.add_argument("--import-csv", nargs=2, metavar=("PRICES_CSV", "USDCAD_CSV"), required=True)
    args = parser.parse_args()

    prices_csv, usdcad_csv = args.import_csv
    conn = connect()
    yahoo = upsert(conn, pd.read_csv(prices_csv, index_col=0, parse_dates=True), "yahoo")
    boc = upsert(conn, pd.read_csv(usdcad_csv, index_col=0, parse_dates=True), "boc")
    print(f"Imported {yahoo:,} Yahoo rows and {boc:,} Bank of Canada rows into {DB_PATH}")


if __name__ == "__main__":
    main()
