# ETF Analytics Report

**Data:** 2021-11-15 to 2026-11-24, 1,224 trading days when the TSX, the NYSE and the Bank of Canada were all open.  
**Generated:** 2026-11-25  
**Sharpe ratio risk-free rate (assumption):** 0.0% per year

## 1. Summary

Each ETF is measured in its own trading currency, with dividends included.

| ETF | Annual return | Volatility | Max drawdown | Sharpe | Beta vs SPY |
|---|---:|---:|---:|---:|---:|
| VFV (S&P 500, CAD) | 13.1% | 15.8% | -22.2% | 0.89 | 0.83 |
| SPY (S&P 500, USD) | 10.4% | 17.7% | -24.5% | 0.67 | 1.00 |
| XIU (TSX 60) | 12.4% | 13.4% | -16.4% | 0.97 | 0.59 |
| XIC (TSX Composite) | 12.2% | 13.7% | -16.2% | 0.93 | 0.61 |
| QQQ (Nasdaq 100, USD) | 10.7% | 24.0% | -35.1% | 0.56 | 1.29 |

![Cumulative return](cumulative_returns.png)

![Drawdown](drawdowns.png)

![60-day rolling volatility](rolling_volatility.png)

## 2. VFV vs SPY

SPY is converted to Canadian dollars with the Bank of Canada's daily USD/CAD rate (1.2517 to 1.4296, +14.2% over the period).

|  | Annual return | Volatility | Max drawdown |
|---|---:|---:|---:|
| VFV (S&P 500, CAD) | 13.1% | 15.8% | -22.2% |
| SPY converted to CAD | 13.4% | 17.0% | -22.2% |
| SPY (S&P 500, USD) | 10.4% | 17.7% | -24.5% |

![VFV vs SPY](vfv_vs_spy.png)

### Calendar-year tracking difference

| Year | VFV | SPY in CAD | Difference (pp) |
|---|---:|---:|---:|
| 2022 | -12.6% | -12.6% | +0.00 |
| 2023 | 23.2% | 23.2% | +0.02 |
| 2024 | 35.2% | 35.9% | -0.64 |
| 2025 | 12.2% | 12.1% | +0.05 |
| 2026 YTD | 10.2% | 10.8% | -0.63 |

![Tracking difference by year](tracking_difference.png)

Daily tracking error over the full period is 3.57% (annualized), against 8.59% with Yahoo's CAD=X rate. Neither rate is taken at the 4 p.m. ET market close (the Bank of Canada rate is a daily average), so some timing noise remains. The calendar-year comparison above is the more reliable measure.

## 3. Correlation

![Correlation of daily returns](correlation.png)

## 4. Data notes

Only days when both markets and the Bank of Canada were open are used (1,308 rows before alignment, 1,224 after). Closed in Canada only: 27 days. Closed in the US only: 27 days. Closed in both: 19 days. Both markets open but no Bank of Canada rate: 10 days.

All data checks passed: no missing columns, duplicate or weekend dates, or zero or negative prices; no daily move above 15% (5% for USD/CAD); no price unchanged for 5 days in a row; no gap over 7 calendar days; and the two USD/CAD sources within 3% of each other.
