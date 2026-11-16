# etf-analytics

![tests](https://github.com/fxtiion-sys/etf-analytics/actions/workflows/tests.yml/badge.svg) ![daily update](https://github.com/fxtiion-sys/etf-analytics/actions/workflows/daily.yml/badge.svg)

A Python tool that downloads 5 years of daily prices for Canadian and US ETFs, cleans and aligns them, analyzes returns, risk and correlation, and generates a full report with one command — with a focus on how a CAD-listed S&P 500 ETF (VFV) compares to SPY.

## Question

VFV and SPY both track the S&P 500. For an investor in Canada, how different is buying VFV in Canadian dollars from holding SPY?

## Key findings

Data: 2021-11-15 to 2026-11-13, 1,217 trading days when the TSX, the NYSE and the Bank of Canada were all open.
These findings are as of 2026-11-13. [`reports/report.md`](reports/report.md) and the charts are rebuilt every weekday with the latest data, so their numbers will move from the ones quoted here.

**1. The gap between VFV and SPY is the currency, not the fund.**
VFV returned 14.3% a year and SPY 11.5% a year. Once SPY is converted to Canadian dollars, it returned 14.5% a year — almost exactly VFV. The difference came from USD/CAD rising from 1.2517 to 1.4257 (+13.9%, Bank of Canada) over the period.

![VFV vs SPY](reports/vfv_vs_spy.png)

**2. VFV tracks SPY in CAD closely, with a small expected lag.**
A small lag is expected from VFV's 0.08% fund expense ratio (FER) and the 15% US withholding tax on dividends, because VFV holds the US-listed Vanguard S&P 500 ETF ([Vanguard](https://www.vanguard.ca/en/product/etf/equity/9563/vanguard-sp-500-index-etf), as at Nov 13, 2026).
Converting SPY with the Bank of Canada's official daily rate instead of Yahoo's `CAD=X` cut the daily tracking error from 8.6% to 3.6% (annualized): most of the earlier gap was noise in the exchange rate, not a difference between the funds.

Yearly differences still move by a few tenths of a percentage point, partly because the year-end exchange rate is also a daily average rather than a 4 p.m. close.

![Tracking difference by year](reports/tracking_difference.png)

**3. A weaker Canadian dollar softened losses for Canadian investors.**
The worst drawdown was −22.2% for both VFV and SPY in CAD, against −24.5% for SPY in USD: the US dollar strengthened during the 2022 decline. Canadian equity ETFs were less risky still — XIU and XIC had a maximum drawdown of about −16%, volatility of about 13%, and a beta of about 0.6 to SPY.

The full report with all tables and charts is in [`reports/report.md`](reports/report.md).

## Data

Daily prices from Yahoo Finance via `yfinance`. Prices are adjusted for dividends and splits (`auto_adjust=True`). Daily prices from Yahoo Finance via `yfinance`. Prices are adjusted for dividends and splits (`auto_adjust=True`).
The USD/CAD rate comes from the Bank of Canada [Valet API](https://www.bankofcanada.ca/valet/docs) (series `FXUSDCAD`).
Both are stored in a local SQLite database, `data/etf.db`.

| Ticker | What it is | Why it's here |
|---|---|---|
| XIU.TO | TSX 60 (60 large Canadian companies) | Main Canadian benchmark |
| XIC.TO | TSX Composite (whole Canadian market) | Compare with XIU |
| VFV.TO | S&P 500, traded in CAD | Main subject |
| SPY | S&P 500, traded in USD | Benchmark for VFV |
| QQQ | Nasdaq 100 | A different, tech-heavy comparison |
| USDCAD | Bank of Canada daily USD/CAD rate | Convert SPY to CAD |
| CAD=X | Yahoo USD/CAD rate | Comparison only |

## Method

### Aligning trading calendars

The TSX and NYSE close on different holidays, so joining the two markets leaves gaps. Over the 5-year period:

| Closed | Days | Examples (2026) |
|---|----|---|
| Canada only | 27 | Victoria Day, Canada Day, Civic Holiday, Thanksgiving (Oct) |
| US only | 27 | MLK Day, Memorial Day, Juneteenth, Independence Day |
| Both | 19 | Family Day / Presidents' Day, Good Friday, Labour Day |

I kept only days when **both markets were open** and the Bank of Canada published a rate (1,301 → 1,217 rows). The Bank is closed on 10 days in the period when both markets traded — Remembrance Day and the National Day for Truth and Reconciliation. Forward-filling the missing prices would create fake 0% days on holidays and push that day's real move into the next day's return, distorting volatility and correlation.

### Metrics

All metrics are pure functions in `etf_analytics/metrics.py`:

- **Annualized return**: compound growth rate, using calendar years between the first and last date (holidays were dropped, so a year has fewer than 252 rows)
- **Annualized volatility**: standard deviation of daily returns × √252
- **Maximum drawdown**: worst fall from a previous peak
- **Sharpe ratio**: return per unit of volatility, with a **0% risk-free rate**. It is used only to compare the ETFs with each other.
- **Correlation**: how closely the ETFs move together
- **Beta**: sensitivity to SPY

### Storage and incremental updates

Prices are stored in SQLite in long format, one row per `(date, symbol)`, with that pair as the primary key and a `CHECK (value > 0)` constraint. Writes are upserts inside a transaction, so re-running an update never creates duplicates and a failed batch writes nothing.

Each update downloads only the last 10 days and writes them over what is stored. Yahoo's adjusted prices are recalculated back through history whenever a fund pays a dividend, so the overlapping days are compared with the stored values first: if they differ by more than 0.01%, the whole history is downloaded again. Appending new prices to old, differently scaled ones would silently hide that dividend.

The data ends at the latest date both sources have published. The Bank of Canada publishes its rate at 4:30 p.m. ET, so without this cutoff a run during the trading day would count today as a Bank of Canada holiday.

### Daily update

A GitHub Actions workflow ([`daily.yml`](.github/workflows/daily.yml)) runs every weekday at 23:00 UTC, after both markets close and the Bank of Canada publishes its rate:

1. Restore `data/etf.db` from the Actions cache (if there is none, the next step downloads everything)
2. Fetch new data, retrying up to three times
3. Validate the data
4. Build the report
5. Save the database to the cache — only if every step above passed
6. Commit the updated report

If any step fails, nothing is committed, the cached database is not replaced, and the workflow opens a GitHub issue (or comments on the open one) with a link to the logs.

### Data validation

Before any analysis, `etf_analytics/validate.py` checks the data and stops the pipeline, listing every problem, if something looks wrong:

| Check | Fails when | Largest value in the real data |
|---|---|---|
| Daily move (ETFs) | above 15% | QQQ +12.0% (April 2025) |
| Daily move (USD/CAD) | above 5% | about 2% |
| Frozen price | same value 5 days in a row | 2 days |
| Gap between dates | over 7 calendar days | 6 days (Christmas) |
| Bank of Canada vs Yahoo USD/CAD | differ by over 3% | 1.6% |

It also checks for missing columns, out-of-order, duplicate or weekend dates, and zero or negative prices. The thresholds are set above the largest real values so that real market moves pass and data errors do not.

The weekend check found a real problem: Yahoo's currency feed included a Saturday row with only `CAD=X`, which was being counted as a day when both markets were closed. Weekend rows are now dropped when the data is loaded.

### VFV vs SPY

SPY is converted to Canadian dollars by multiplying its price by the USD/CAD rate, then compared with VFV by calendar year (tracking difference) and day by day (tracking error).

**Limitation:** Neither exchange rate is taken at the 4 p.m. ET market close — the Bank of Canada rate is a daily average — so the day-by-day conversion still adds some timing noise. Switching from Yahoo's `CAD=X` to the Bank of Canada rate lowered the daily tracking error from 8.6% to 3.6%, but the calendar-year comparison remains the more reliable measure.

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python -m etf_analytics.report    # data → metrics → charts → reports/report.md
python -m pytest -v               # run the unit tests
```
For development, install the extra tools and run the same checks as CI:

```bash
python -m pip install -r requirements-dev.txt
ruff check .          # lint
ruff format .         # format
mypy                  # type check
```

The first run downloads all data since 2021-11-15 into `data/etf.db`. After that, `python -m etf_analytics.fetch` downloads only the days since the last update (`--full` downloads everything again). Each step can also be run on its own: `fetch`, `clean`, `validate`, `tracking`, `charts`.

## Tests

Every metric is checked against small series whose answers can be worked out by hand. For example, prices `[100, 110, 99]` must give returns of `+10%` and `−10%` and a maximum drawdown of `−10%`.
The chart and report tests use small fake data with Canadian, US and Bank of Canada holidays, and the Bank of Canada download is tested on a hand-written API response, so the whole suite runs without the network.
Each data check is tested by starting from clean fake data and breaking it on purpose, for example a +20% jump or a price frozen for five days.

GitHub Actions runs two jobs on every pull request: `lint` (ruff lint, ruff format check and mypy type check) and `pytest`.

## Project structure

```
etf-analytics/
├── .github/workflows/tests.yml   # run pytest on every PR and push to main
├── .github/workflows/daily.yml   # weekday data update and report
├── data/etf.db                   # SQLite database (not committed)
├── pyproject.toml                # ruff and mypy settings
├── requirements-dev.txt          # ruff and mypy, pinned
├── etf_analytics/
│   ├── fx.py                     # Bank of Canada USD/CAD rate
│   ├── clean.py                  # align TSX/NYSE trading calendars
│   ├── validate.py               # data checks before analysis
│   ├── metrics.py                # return, risk and correlation metrics
│   ├── fetch.py                  # download + incremental update
│   ├── storage.py                # SQLite storage
│   ├── tracking.py               # VFV vs SPY in CAD
│   ├── charts.py                 # PNG charts
│   └── report.py                 # one-command Markdown report
├── tests/                        # unit and smoke tests
├── reports/                      # report.md + charts
└── requirements.txt
```