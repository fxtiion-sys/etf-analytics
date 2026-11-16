"""Charts saved as PNG files. Each plot function takes data and an output path, and only draws."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import matplotlib

matplotlib.use("Agg")  # draw to files only; no window needed

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import PercentFormatter

from etf_analytics import fx, metrics, tracking

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
ETFS = ["VFV.TO", "SPY", "XIU.TO", "XIC.TO", "QQQ"]

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"

# Colour follows the ticker, so each ETF has the same colour in every chart.
COLORS = {
    "VFV.TO": "#2a78d6",
    "SPY": "#eb6834",
    "XIU.TO": "#1baf7a",
    "XIC.TO": "#eda100",
    "QQQ": "#e87ba4",
    "SPY_CAD": "#008300",
}
LABELS = {
    "VFV.TO": "VFV (S&P 500, CAD)",
    "SPY": "SPY (S&P 500, USD)",
    "XIU.TO": "XIU (TSX 60)",
    "XIC.TO": "XIC (TSX Composite)",
    "QQQ": "QQQ (Nasdaq 100, USD)",
    "SPY_CAD": "SPY converted to CAD",
}
POSITIVE = "#2a78d6"
NEGATIVE = "#e34948"
SEQUENTIAL = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])


def _new_axes(title: str, subtitle: str | None = None) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    fig.suptitle(title, x=0.01, ha="left", color=TEXT, fontsize=14, fontweight="bold")
    if subtitle:
        ax.set_title(subtitle, loc="left", color=TEXT_SECONDARY, fontsize=10)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def _plot_series(ax: plt.Axes, data: pd.DataFrame) -> None:
    for column in data.columns:
        ax.plot(data.index, data[column], color=COLORS[column], linewidth=2, label=LABELS[column])
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    _legend(ax, "upper left")


LegendLocation = Literal["upper left", "upper right", "lower right"]


def _legend(ax: plt.Axes, loc: LegendLocation) -> None:
    # A surface-coloured box keeps the legend readable if a line passes behind it.
    ax.legend(
        loc=loc,
        fontsize=9,
        labelcolor=TEXT_SECONDARY,
        frameon=True,
        facecolor=SURFACE,
        edgecolor="none",
        framealpha=0.9,
    )


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def cumulative_returns(prices: pd.DataFrame, path: Path) -> Path:
    growth = prices / prices.iloc[0] - 1
    fig, ax = _new_axes("Cumulative return", "Each ETF in its own trading currency, dividends included")
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=0.8)
    _plot_series(ax, growth)
    return _save(fig, path)


def drawdowns(prices: pd.DataFrame, path: Path) -> Path:
    fig, ax = _new_axes("Drawdown", "How far each ETF was below its previous peak")
    _plot_series(ax, metrics.drawdown(prices))
    _legend(ax, "lower right")
    return _save(fig, path)


def rolling_volatility(prices: pd.DataFrame, path: Path, window: int = 60) -> Path:
    returns = metrics.daily_returns(prices)
    volatility = returns.rolling(window).std() * np.sqrt(metrics.TRADING_DAYS)
    fig, ax = _new_axes(f"{window}-day rolling volatility", "Annualized standard deviation of daily returns")
    _plot_series(ax, volatility.dropna())
    ax.set_ylim(bottom=0)
    _legend(ax, "upper right")
    return _save(fig, path)


def correlation_heatmap(prices: pd.DataFrame, path: Path) -> Path:
    corr = metrics.correlation_matrix(metrics.daily_returns(prices))
    labels = [LABELS[t].split(" (")[0] for t in corr.columns]
    fig, ax = plt.subplots(figsize=(7, 6))
    fig.patch.set_facecolor(SURFACE)
    fig.suptitle("Correlation of daily returns", x=0.02, ha="left", color=TEXT, fontsize=14, fontweight="bold")
    mesh = ax.pcolormesh(corr.values, cmap=SEQUENTIAL, vmin=0, vmax=1, edgecolors=SURFACE, linewidth=2)
    ax.invert_yaxis()
    ax.set_xticks(np.arange(len(labels)) + 0.5, labels)
    ax.set_yticks(np.arange(len(labels)) + 0.5, labels)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=10, length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for i in range(len(labels)):
        for j in range(len(labels)):
            value = corr.values[i, j]
            ax.text(
                j + 0.5,
                i + 0.5,
                f"{value:.2f}",
                ha="center",
                va="center",
                fontsize=10,
                color="white" if value > 0.6 else TEXT,
            )
    colorbar = fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
    colorbar.outline.set_visible(False)
    colorbar.ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    return _save(fig, path)


def vfv_vs_spy_growth(vfv: pd.Series, spy_cad: pd.Series, spy_usd: pd.Series, path: Path) -> Path:
    data = pd.concat([vfv.rename("VFV.TO"), spy_cad.rename("SPY_CAD"), spy_usd.rename("SPY")], axis=1)
    fig, ax = _new_axes(
        "VFV vs SPY: the gap is the currency", "Cumulative return. SPY converted to CAD lands on top of VFV."
    )
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=0.8)
    _plot_series(ax, data / data.iloc[0] - 1)
    return _save(fig, path)


def tracking_difference(yearly_difference: pd.Series, path: Path, ytd_year: int | None = None) -> Path:
    points = yearly_difference * 100  # percentage points
    labels = [f"{year} YTD" if year == ytd_year else str(year) for year in points.index]
    colors = [POSITIVE if value >= 0 else NEGATIVE for value in points]
    fig, ax = _new_axes("VFV minus SPY in CAD, by calendar year", "Above 0: VFV did better. Below 0: VFV lagged.")
    bars = ax.bar(labels, points, color=colors, width=0.6)
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=0.8)
    for bar, value in zip(bars, points, strict=True):
        offset = 0.02 if value >= 0 else -0.02
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + offset,
            f"{value:+.2f} pp",
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=10,
            color=TEXT,
        )
    limit = max(abs(points.min()), abs(points.max())) * 1.4
    ax.set_ylim(-limit, limit)
    ax.set_ylabel("percentage points", color=TEXT_SECONDARY)
    return _save(fig, path)


def make_all_charts(prices: pd.DataFrame, out_dir: Path = REPORTS_DIR) -> dict[str, Path]:
    """Draw every chart from aligned prices (including the USD/CAD column) and return their paths."""
    etfs = prices[ETFS]
    spy_cad = tracking.to_cad(prices["SPY"], prices[fx.COLUMN])
    yearly = tracking.tracking_difference(prices["VFV.TO"], spy_cad)
    return {
        "cumulative_returns": cumulative_returns(etfs, out_dir / "cumulative_returns.png"),
        "drawdowns": drawdowns(etfs, out_dir / "drawdowns.png"),
        "rolling_volatility": rolling_volatility(etfs, out_dir / "rolling_volatility.png"),
        "correlation": correlation_heatmap(etfs, out_dir / "correlation.png"),
        "vfv_vs_spy": vfv_vs_spy_growth(prices["VFV.TO"], spy_cad, prices["SPY"], out_dir / "vfv_vs_spy.png"),
        "tracking_difference": tracking_difference(
            yearly, out_dir / "tracking_difference.png", ytd_year=prices.index[-1].year
        ),
    }


def main() -> None:
    from etf_analytics.clean import align_trading_days
    from etf_analytics.fetch import load_data

    for name, path in make_all_charts(align_trading_days(load_data())).items():
        print(f"{name:20s} {path}")


if __name__ == "__main__":
    main()
