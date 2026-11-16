"""Tests for the SQLite storage, using an in-memory database."""

import numpy as np
import pandas as pd
import pytest

from etf_analytics import storage


def wide(values: dict[str, list[float]], dates: list[str]) -> pd.DataFrame:
    return pd.DataFrame(values, index=pd.to_datetime(dates))


def test_upsert_and_read_back_skips_empty_cells():
    conn = storage.connect(":memory:")
    table = wide({"SPY": [100.0, 101.0], "VFV.TO": [np.nan, 50.0]}, ["2024-07-01", "2024-07-02"])

    assert storage.upsert(conn, table, "yahoo") == 3  # the empty VFV cell is not stored

    result = storage.read_wide(conn)
    assert list(result.columns) == ["SPY", "VFV.TO"]
    assert result.loc["2024-07-02", "VFV.TO"] == pytest.approx(50.0)
    assert np.isnan(result.loc["2024-07-01", "VFV.TO"])


def test_upsert_replaces_existing_value_instead_of_duplicating():
    conn = storage.connect(":memory:")
    storage.upsert(conn, wide({"SPY": [100.0]}, ["2024-07-02"]), "yahoo")
    storage.upsert(conn, wide({"SPY": [99.5]}, ["2024-07-02"]), "yahoo")

    (count,) = conn.execute("SELECT COUNT(*) FROM prices").fetchone()
    assert count == 1
    assert storage.read_wide(conn).loc["2024-07-02", "SPY"] == pytest.approx(99.5)


def test_last_date_is_tracked_per_source():
    conn = storage.connect(":memory:")
    assert storage.last_date(conn, "yahoo") is None

    storage.upsert(conn, wide({"SPY": [100.0, 101.0]}, ["2024-07-01", "2024-07-02"]), "yahoo")
    storage.upsert(conn, wide({"USDCAD": [1.37]}, ["2024-06-28"]), "boc")

    assert storage.last_date(conn, "yahoo") == pd.Timestamp("2024-07-02")
    assert storage.last_date(conn, "boc") == pd.Timestamp("2024-06-28")


def test_database_rejects_non_positive_prices():
    conn = storage.connect(":memory:")
    with pytest.raises(Exception, match="CHECK constraint failed"):
        storage.upsert(conn, wide({"SPY": [100.0, -1.0]}, ["2024-07-01", "2024-07-02"]), "yahoo")
    assert storage.last_date(conn, "yahoo") is None  # the whole batch was rolled back
