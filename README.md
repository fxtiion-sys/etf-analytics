# etf-analytics

A Python tool that downloads 5 years of daily prices for Canadian and US ETFs, cleans and aligns them, and analyzes returns, risk and correlation — with a focus on how a CAD-listed S&P 500 ETF (VFV) compares to SPY.

## Question

VFV and SPY both track the S&P 500. For an investor in Canada, how different is buying VFV in Canadian dollars from holding SPY?

## Data

Daily prices from Yahoo Finance via `yfinance`, 2021-11-15 to 2026-11-14. Prices are adjusted for dividends and splits (`auto_adjust=True`). The raw download is cached in `data/raw/prices.csv` so results are reproducible without the network.

| Ticker | What it is | Why it's here |
|---|---|---|
| XIU.TO | TSX 60 (60 large Canadian companies) | Main Canadian benchmark |
| XIC.TO | TSX Composite (whole Canadian market) | Compare with XIU |
| VFV.TO | S&P 500, traded in CAD | Main subject |
| SPY | S&P 500, traded in USD | Benchmark for VFV |
| QQQ | Nasdaq 100 | A different, tech-heavy comparison |
| CAD=X | USD/CAD exchange rate | Convert SPY to CAD |

## Method

### Aligning trading calendars

The TSX and NYSE close on different holidays, so joining the two markets leaves gaps. Over the 5-year period:

| Closed | Days | Examples (2026) |
|---|---|---|
| Canada only | 27 | Victoria Day, Canada Day, Civic Holiday, Thanksgiving (Oct) |
| US only | 27 | MLK Day, Memorial Day, Juneteenth, Independence Day |
| Both | 20 | Family Day / Presidents' Day, Good Friday, Labour Day |

I kept only days when **both markets were open** (1,302 → 1,227 rows). Forward-filling the missing prices would create fake 0% days on holidays and push that day's real move into the next day's return, distorting volatility and correlation.

### Metrics

All metrics are pure functions in `etf_analytics/metrics.py`:

- **Annualized return** — compound growth rate, using calendar years between the first and last date (holidays were dropped, so a year has fewer than 252 rows)
- **Annualized volatility** — standard deviation of daily returns × √252
- **Maximum drawdown** — worst fall from a previous peak
- **Sharpe ratio** — excess return per unit of volatility (risk-free rate assumption: _TBD_)
- **Correlation** — how closely the ETFs move together
- **Beta** — sensitivity to SPY

## Key findings

_To be added after the VFV vs SPY tracking analysis._

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python -m etf_analytics.fetch     # download prices (or load the cached CSV)
python -m etf_analytics.clean     # show holiday alignment
python -m pytest -v               # run the unit tests
```

Use `python -m etf_analytics.fetch --refresh` to download fresh data.

## Tests

`tests/test_metrics.py` checks every metric against small series whose answers can be worked out by hand. For example, prices `[100, 110, 99]` must give returns of `+10%` and `−10%` and a maximum drawdown of `−10%`.

## Project structure

```
etf-analytics/
├── data/raw/            # cached price CSV
├── etf_analytics/
│   ├── fetch.py         # download + cache
│   ├── clean.py         # align trading calendars
│   ├── metrics.py       # metric functions
│   ├── charts.py        # charts (coming)
│   └── report.py        # report generation (coming)
├── tests/test_metrics.py
├── reports/             # generated report + charts
└── requirements.txt
```