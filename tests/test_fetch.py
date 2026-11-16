"""Tests for the incremental update, using fake downloaders instead of the network."""

from datetime import date

import pandas as pd
import pytest

from etf_analytics import fetch, storage


class FakeYahoo:
    """Returns prices from a fixed table and remembers which start dates were requested."""

    def __init__(self, table: pd.DataFrame) -> None:
        self.table = table
        self.starts: list[date] = []

    def __call__(self, start: date, end: date) -> pd.DataFrame:
        self.starts.append(start)
        return self.table.loc[pd.Timestamp(start) : pd.Timestamp(end)]


def prices(days: int, scale: float = 1.0) -> pd.DataFrame:
    idx = pd.bdate_range("2021-11-15", periods=days)
    return pd.DataFrame({"SPY": [(100.0 + i) * scale for i in range(days)]}, index=idx)


def test_empty_database_downloads_everything_from_start_date():
    conn = storage.connect(":memory:")
    yahoo = FakeYahoo(prices(30))

    message = fetch.update_prices(conn, date(2021, 12, 31), download=yahoo)

    assert yahoo.starts == [fetch.START_DATE]
    assert "full reload (empty database)" in message
    assert len(storage.read_wide(conn)) == 30


def test_update_only_downloads_recent_days_and_appends():
    conn = storage.connect(":memory:")
    storage.upsert(conn, prices(30).iloc[:20], "yahoo")  # database is 10 days behind
    yahoo = FakeYahoo(prices(30))

    message = fetch.update_prices(conn, date(2021, 12, 31), download=yahoo)

    last_stored = prices(30).index[19]
    assert yahoo.starts == [(last_stored - pd.Timedelta(days=fetch.OVERLAP_DAYS)).date()]
    assert "incremental" in message
    assert len(storage.read_wide(conn)) == 30


def test_rescaled_history_triggers_full_reload():
    conn = storage.connect(":memory:")
    storage.upsert(conn, prices(20), "yahoo")
    # A dividend was paid: Yahoo now returns every past adjusted price 1% lower.
    yahoo = FakeYahoo(prices(30, scale=0.99))

    message = fetch.update_prices(conn, date(2021, 12, 31), download=yahoo)

    assert "full reload (adjusted history changed)" in message
    assert yahoo.starts[-1] == fetch.START_DATE
    assert storage.read_wide(conn).iloc[0]["SPY"] == pytest.approx(99.0)  # old values replaced


def test_weekend_rows_are_not_stored():
    conn = storage.connect(":memory:")
    saturday = pd.DataFrame({"SPY": [100.0, 101.0]}, index=pd.to_datetime(["2021-11-19", "2021-11-20"]))

    fetch.update_prices(conn, date(2021, 11, 20), download=FakeYahoo(saturday))

    assert list(storage.read_wide(conn).index) == [pd.Timestamp("2021-11-19")]


def test_usdcad_update_starts_from_overlap():
    conn = storage.connect(":memory:")
    storage.upsert(conn, pd.DataFrame({"USDCAD": [1.35]}, index=pd.to_datetime(["2024-07-15"])), "boc")
    starts: list[date] = []

    def fake_boc(start: date, end: date) -> pd.Series:
        starts.append(start)
        return pd.Series([1.36], index=pd.to_datetime(["2024-07-16"]), name="USDCAD")

    fetch.update_usdcad(conn, date(2024, 7, 16), download=fake_boc)

    assert starts == [date(2024, 7, 5)]
    assert storage.last_date(conn, "boc") == pd.Timestamp("2024-07-16")


def test_load_data_stops_at_latest_date_both_sources_have():
    conn = storage.connect(":memory:")
    days = pd.to_datetime(["2024-07-15", "2024-07-16"])
    storage.upsert(conn, pd.DataFrame({t: [1.0, 2.0] for t in fetch.TICKERS}, index=days), "yahoo")
    storage.upsert(conn, pd.DataFrame({"USDCAD": [1.37]}, index=days[:1]), "boc")  # 07-16 not published yet

    assert list(fetch.load_data(conn).index) == [pd.Timestamp("2024-07-15")]
