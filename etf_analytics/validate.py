"""Check the price table before any analysis runs, and stop the pipeline if something looks wrong."""

from __future__ import annotations

import pandas as pd

from etf_analytics import fx
from etf_analytics.fetch import TICKERS

REQUIRED_COLUMNS = [*TICKERS, fx.COLUMN]
FX_COLUMNS = ["CAD=X", fx.COLUMN]

MAX_DAILY_MOVE = 0.15  # largest real ETF move in the data: QQQ +12.0% (April 2025)
MAX_FX_DAILY_MOVE = 0.05  # largest real USD/CAD move in the data: about 2%
STALE_DAYS = 5  # the same price on 5 trading days in a row means a frozen feed
MAX_GAP_DAYS = 7  # longest real gap is 6 calendar days, over Christmas
MAX_FX_DIFFERENCE = 0.03  # Bank of Canada vs Yahoo USD/CAD; the real maximum is about 1.6%


class DataValidationError(Exception):
    """Raised when the data fails one or more checks."""


def check_raw(prices: pd.DataFrame) -> list[str]:
    """Structural checks on the table as loaded, before calendars are aligned."""
    issues = []
    missing = [c for c in REQUIRED_COLUMNS if c not in prices.columns]
    if missing:
        issues.append(f"missing columns: {missing}")
    if not prices.index.is_monotonic_increasing:
        issues.append("dates are not in order")
    if prices.index.has_duplicates:
        issues.append(f"duplicate dates: {_dates(prices.index[prices.index.duplicated()])}")
    weekends = prices.index[prices.index.day_of_week >= 5]
    if len(weekends):
        issues.append(f"weekend dates: {_dates(weekends)}")
    for col in prices.columns:
        bad = prices.index[prices[col] <= 0]
        if len(bad):
            issues.append(f"{col}: zero or negative values on {_dates(bad)}")
    return issues


def check_aligned(prices: pd.DataFrame) -> list[str]:
    """Checks on the aligned table: jumps, frozen prices, gaps and the two FX sources."""
    issues = []
    returns = prices.pct_change()
    for col in prices.columns:
        limit = MAX_FX_DAILY_MOVE if col in FX_COLUMNS else MAX_DAILY_MOVE
        jumps = returns[col][returns[col].abs() > limit]
        for day, move in jumps.items():
            issues.append(f"{col}: daily move of {move:+.1%} on {day.date()} is larger than {limit:.0%}")

        run_id = (prices[col] != prices[col].shift()).cumsum()
        run_length = prices[col].groupby(run_id).transform("size")
        stale = prices.index[run_length >= STALE_DAYS]
        if len(stale):
            issues.append(f"{col}: same value on {STALE_DAYS}+ days in a row, starting {stale[0].date()}")

    gaps = prices.index.to_series().diff().dt.days
    for day, days in gaps[gaps > MAX_GAP_DAYS].items():
        issues.append(f"gap of {days:.0f} calendar days before {day.date()}")

    if set(FX_COLUMNS) <= set(prices.columns):
        difference = (prices[fx.COLUMN] / prices["CAD=X"] - 1).abs()
        far = difference[difference > MAX_FX_DIFFERENCE]
        if len(far):
            issues.append(
                f"Bank of Canada and Yahoo USD/CAD differ by more than {MAX_FX_DIFFERENCE:.0%} "
                f"on {len(far)} days, e.g. {_dates(far.index)}"
            )
    return issues


def validate(raw: pd.DataFrame, aligned: pd.DataFrame) -> None:
    """Run every check and raise DataValidationError listing all problems found."""
    issues = check_raw(raw) + check_aligned(aligned)
    if issues:
        raise DataValidationError("Data failed validation:\n- " + "\n- ".join(issues))


def _dates(index: pd.Index, limit: int = 3) -> str:
    shown = ", ".join(str(d.date()) for d in index[:limit])
    return shown + (f" (+{len(index) - limit} more)" if len(index) > limit else "")


def main() -> None:
    from etf_analytics.clean import align_trading_days
    from etf_analytics.fetch import load_data

    raw = load_data()
    aligned = align_trading_days(raw)
    validate(raw, aligned)
    print(f"All checks passed ({len(raw):,} raw rows, {len(aligned):,} aligned rows).")


if __name__ == "__main__":
    main()
