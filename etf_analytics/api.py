"""Read-only REST API over the price database.

Run it with `python -m etf_analytics.api` and open http://127.0.0.1:8000/docs.
The API only reads data/etf.db. Updating the data is the job of `python -m etf_analytics.fetch`.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from etf_analytics import metrics, storage
from etf_analytics.clean import align_trading_days
from etf_analytics.fetch import load_data
from etf_analytics.report import RISK_FREE_RATE


class Etf(BaseModel):
    symbol: str  # short name used in URLs, e.g. VFV
    ticker: str  # Yahoo Finance ticker, e.g. VFV.TO
    index: str  # the index the fund follows
    currency: str  # currency the fund trades in
    first_date: date
    last_date: date


class Metrics(BaseModel):
    symbol: str
    currency: str
    start: date
    end: date
    trading_days: int
    annual_return: float
    annual_volatility: float
    max_drawdown: float
    sharpe: float
    beta_vs_spy: float


class Price(BaseModel):
    date: date
    close: float  # adjusted close (dividends included), in the fund's own currency


# symbol -> (ticker, index, currency), in the same order as the report
ETFS = {
    "VFV": ("VFV.TO", "S&P 500", "CAD"),
    "SPY": ("SPY", "S&P 500", "USD"),
    "XIU": ("XIU.TO", "S&P/TSX 60", "CAD"),
    "XIC": ("XIC.TO", "S&P/TSX Composite", "CAD"),
    "QQQ": ("QQQ", "Nasdaq-100", "USD"),
}

app = FastAPI(title="ETF Analytics API", description="Prices and metrics for five Canadian and US ETFs.")


def get_prices() -> pd.DataFrame:
    """Load the stored table for one request. Tests replace this with fake data."""
    conn = storage.connect(storage.DB_PATH)
    try:
        if storage.last_date(conn, "yahoo") is None or storage.last_date(conn, "boc") is None:
            # load_data would start a full download here; an API request should never do that.
            raise HTTPException(503, "The database is empty. Run `python -m etf_analytics.fetch` first.")
        return load_data(conn)
    finally:
        conn.close()


Prices = Annotated[pd.DataFrame, Depends(get_prices)]


def find_etf(symbol: str) -> tuple[str, str, str, str]:
    """Return (symbol, ticker, index, currency). Accepts lower case. Unknown symbols give 404."""
    key = symbol.upper()
    if key not in ETFS:
        raise HTTPException(404, f"Unknown ETF {symbol!r}. Available: {', '.join(ETFS)}")
    return (key, *ETFS[key])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/etfs")
def list_etfs(prices: Prices) -> list[Etf]:
    """Every ETF with the first and last date stored for it."""
    result = []
    for symbol, (ticker, index, currency) in ETFS.items():
        days = prices[ticker].dropna().index
        result.append(
            Etf(
                symbol=symbol,
                ticker=ticker,
                index=index,
                currency=currency,
                first_date=days[0].date(),
                last_date=days[-1].date(),
            )
        )
    return result


@app.get("/etfs/{symbol}/metrics")
def etf_metrics(symbol: str, prices: Prices) -> Metrics:
    """Headline metrics over the whole period. Same numbers as the summary table in the report."""
    key, ticker, _, currency = find_etf(symbol)
    aligned = align_trading_days(prices)
    tickers = [t for t, _, _ in ETFS.values()]
    row = metrics.summary_table(aligned[tickers], market="SPY", risk_free_rate=RISK_FREE_RATE).loc[ticker]
    return Metrics(
        symbol=key,
        currency=currency,
        start=aligned.index[0].date(),
        end=aligned.index[-1].date(),
        trading_days=len(aligned),
        annual_return=row["annual_return"],
        annual_volatility=row["annual_volatility"],
        max_drawdown=row["max_drawdown"],
        sharpe=row["sharpe"],
        beta_vs_spy=row["beta_vs_SPY"],
    )


@app.get("/etfs/{symbol}/prices")
def etf_prices(
    symbol: str,
    prices: Prices,
    start: Annotated[date | None, Query(description="First date, YYYY-MM-DD")] = None,
    end: Annotated[date | None, Query(description="Last date, YYYY-MM-DD")] = None,
) -> list[Price]:
    """Daily closes for one ETF, optionally between two dates (inclusive)."""
    _, ticker, _, _ = find_etf(symbol)
    if start and end and start > end:
        raise HTTPException(400, "start must be on or before end.")
    closes = prices[ticker].dropna()
    if start:
        closes = closes[closes.index >= pd.Timestamp(start)]
    if end:
        closes = closes[closes.index <= pd.Timestamp(end)]
    return [Price(date=day.date(), close=value) for day, value in closes.items()]


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
