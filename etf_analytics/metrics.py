"""Performance and risk metrics. Pure functions: prices or returns in, numbers out."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def daily_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Simple daily returns. The first row has no previous price, so it is dropped."""
    return prices.pct_change().iloc[1:]


def annualized_return(prices: pd.Series) -> float:
    """Compound annual growth rate, using calendar time between the first and last date.

    Calendar years are used instead of row count because holidays were dropped,
    so a year has fewer than 252 rows in this dataset.
    """
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    return (prices.iloc[-1] / prices.iloc[0]) ** (1 / years) - 1


def annualized_volatility(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    """Standard deviation of daily returns scaled to one year."""
    return returns.std() * np.sqrt(periods)


def drawdown(prices: pd.Series) -> pd.Series:
    """Percentage below the highest price seen so far (0 at a new high)."""
    return prices / prices.cummax() - 1


def max_drawdown(prices: pd.Series) -> float:
    """Worst peak-to-trough fall, as a negative number."""
    return drawdown(prices).min()


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods: int = TRADING_DAYS) -> float:
    """Annualized excess return per unit of volatility. risk_free_rate is an annual assumption."""
    excess = returns - risk_free_rate / periods
    return excess.mean() / excess.std() * np.sqrt(periods)


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Pairwise correlation of daily returns."""
    return returns.corr()


def beta(asset_returns: pd.Series, market_returns: pd.Series) -> float:
    """Sensitivity to the market: cov(asset, market) / var(market)."""
    pair = pd.concat([asset_returns, market_returns], axis=1, keys=["asset", "market"]).dropna()
    return pair["asset"].cov(pair["market"]) / pair["market"].var()


def summary_table(prices: pd.DataFrame, market: str = "SPY", risk_free_rate: float = 0.0) -> pd.DataFrame:
    """One row per ticker with the headline metrics."""
    returns = daily_returns(prices)
    rows = {
        ticker: {
            "annual_return": annualized_return(prices[ticker]),
            "annual_volatility": annualized_volatility(returns[ticker]),
            "max_drawdown": max_drawdown(prices[ticker]),
            "sharpe": sharpe_ratio(returns[ticker], risk_free_rate),
            f"beta_vs_{market}": beta(returns[ticker], returns[market]),
        }
        for ticker in prices.columns
    }
    return pd.DataFrame(rows).T