"""Build reports/report.md in one command: prices -> metrics -> tracking -> charts -> Markdown."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from etf_analytics import charts, fx, metrics, tracking
from etf_analytics.clean import align_trading_days, holiday_mismatches, missing_fx_days

RISK_FREE_RATE = 0.0  # annual assumption for the Sharpe ratio; stated in the report and README

METRIC_NAMES = {
    "annual_return": "Annual return",
    "annual_volatility": "Volatility",
    "max_drawdown": "Max drawdown",
    "sharpe": "Sharpe",
    "beta_vs_SPY": "Beta vs SPY",
}
PERCENT = "{:.1%}"
NUMBER = "{:.2f}"
METRIC_FORMATS = {
    "Annual return": PERCENT,
    "Volatility": PERCENT,
    "Max drawdown": PERCENT,
    "Sharpe": NUMBER,
    "Beta vs SPY": NUMBER,
}


def markdown_table(df: pd.DataFrame, formats: dict[str, str], index_name: str = "") -> str:
    """Render a DataFrame as a Markdown table. formats maps a column to a format like '{:.1%}'."""
    header = "| " + " | ".join([index_name, *map(str, df.columns)]) + " |"
    divider = "|---|" + "---:|" * len(df.columns)
    rows = [
        "| " + " | ".join([str(label), *(formats.get(col, "{}").format(row[col]) for col in df.columns)]) + " |"
        for label, row in df.iterrows()
    ]
    return "\n".join([header, divider, *rows])


def build_report(raw_prices: pd.DataFrame, out_dir: Path = charts.REPORTS_DIR) -> Path:
    """Run the whole analysis on raw prices and write report.md plus charts to out_dir."""
    prices = align_trading_days(raw_prices)
    start, end = prices.index[0].date(), prices.index[-1].date()
    chart_paths = charts.make_all_charts(prices, out_dir)

    # Summary of the five ETFs, each in its own trading currency
    summary = metrics.summary_table(prices[charts.ETFS], market="SPY", risk_free_rate=RISK_FREE_RATE)
    summary = summary.rename(index=charts.LABELS, columns=METRIC_NAMES)

    # VFV vs SPY, with SPY converted to Canadian dollars
    spy_cad = tracking.to_cad(prices["SPY"], prices[fx.COLUMN]).rename("SPY_CAD")
    compare = pd.concat([prices["VFV.TO"], spy_cad, prices["SPY"]], axis=1)
    compare_summary = metrics.summary_table(compare, market="SPY_CAD", risk_free_rate=RISK_FREE_RATE)
    compare_summary = compare_summary[["annual_return", "annual_volatility", "max_drawdown"]]
    compare_summary = compare_summary.rename(index=charts.LABELS, columns=METRIC_NAMES)

    yearly = pd.DataFrame({
        "VFV": tracking.calendar_year_returns(prices["VFV.TO"]),
        "SPY in CAD": tracking.calendar_year_returns(spy_cad),
    })
    yearly["Difference (pp)"] = (yearly["VFV"] - yearly["SPY in CAD"]) * 100
    yearly.index = [f"{year} YTD" if year == end.year else str(year) for year in yearly.index]

    returns = metrics.daily_returns(compare)
    daily_te = (returns["VFV.TO"] - returns["SPY_CAD"]).std() * np.sqrt(metrics.TRADING_DAYS)

    usdcad = prices[fx.COLUMN]
    fx_change = usdcad.iloc[-1] / usdcad.iloc[0] - 1
    yahoo_cad = tracking.to_cad(prices["SPY"], prices["CAD=X"])
    yahoo_te = (returns["VFV.TO"] - metrics.daily_returns(yahoo_cad)).std() * np.sqrt(metrics.TRADING_DAYS)

    holidays = holiday_mismatches(raw_prices)
    no_fx = missing_fx_days(raw_prices)

    def image(name: str, alt: str) -> str:
        return f"![{alt}]({chart_paths[name].name})"

    lines = [
        "# ETF Analytics Report",
        "",
        f"**Data:** {start} to {end}, {len(prices):,} trading days when the TSX, the NYSE "
        "and the Bank of Canada were all open.  ",        f"**Generated:** {date.today()}  ",
        f"**Sharpe ratio risk-free rate (assumption):** {RISK_FREE_RATE:.1%} per year",
        "",
        "## 1. Summary",
        "",
        "Each ETF is measured in its own trading currency, with dividends included.",
        "",
        markdown_table(summary, METRIC_FORMATS, "ETF"),
        "",
        image("cumulative_returns", "Cumulative return"),
        "",
        image("drawdowns", "Drawdown"),
        "",
        image("rolling_volatility", "60-day rolling volatility"),
        "",
        "## 2. VFV vs SPY",
        "",
        "SPY is converted to Canadian dollars with the Bank of Canada's daily USD/CAD rate "
        f"({usdcad.iloc[0]:.4f} to {usdcad.iloc[-1]:.4f}, {fx_change:+.1%} over the period).",
        "",
        markdown_table(compare_summary, METRIC_FORMATS),
        "",
        image("vfv_vs_spy", "VFV vs SPY"),
        "",
        "### Calendar-year tracking difference",
        "",
        markdown_table(yearly, {"VFV": PERCENT, "SPY in CAD": PERCENT, "Difference (pp)": "{:+.2f}"}, "Year"),
        "",
        image("tracking_difference", "Tracking difference by year"),
        "",
        f"Daily tracking error over the full period is {daily_te:.2%} (annualized), against {yahoo_te:.2%} "
        "with Yahoo's CAD=X rate. Neither rate is taken at the 4 p.m. ET market close (the Bank of Canada "
        "rate is a daily average), so some timing noise remains. The calendar-year comparison above is "
        "the more reliable measure.",
        "",
        "## 3. Correlation",
        "",
        image("correlation", "Correlation of daily returns"),
        "",
        "## 4. Data notes",
        "",
        "Only days when both markets and the Bank of Canada were open are used "
        f"({len(raw_prices):,} rows before alignment, "
        f"{len(prices):,} after). Closed in Canada only: {len(holidays['canada_only'])} days. "
        f"Closed in the US only: {len(holidays['us_only'])} days. Closed in both: {len(holidays['both'])} days. "
        f"Both markets open but no Bank of Canada rate: {len(no_fx)} days.",
        "",
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    from etf_analytics.fetch import load_data

    print(f"Report written to {build_report(load_data())}")


if __name__ == "__main__":
    main()