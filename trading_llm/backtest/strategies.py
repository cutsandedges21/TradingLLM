"""Built-in, long/flat strategies for the backtester.

Each strategy takes an OHLC DataFrame and returns a target-position Series aligned
to the index, with values in {0.0, 1.0} (fully invested long, or flat). Long/flat
keeps results beginner-legible and avoids shorting complexity. Strategies reuse the
local indicator math in ``market.indicators``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from trading_llm.market import indicators as ind


def _buy_hold(df: pd.DataFrame, **_) -> pd.Series:
    return pd.Series(1.0, index=df.index)


def _sma_cross(df: pd.DataFrame, fast: int = 20, slow: int = 50, **_) -> pd.Series:
    close = df["close"]
    sig = (ind.sma(close, int(fast)) > ind.sma(close, int(slow))).astype(float)
    return sig.fillna(0.0)


def _ema_cross(df: pd.DataFrame, fast: int = 12, slow: int = 26, **_) -> pd.Series:
    close = df["close"]
    sig = (ind.ema(close, int(fast)) > ind.ema(close, int(slow))).astype(float)
    return sig.fillna(0.0)


def _price_above_sma(df: pd.DataFrame, period: int = 200, **_) -> pd.Series:
    close = df["close"]
    sig = (close > ind.sma(close, int(period))).astype(float)
    return sig.fillna(0.0)


def _macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, **_) -> pd.Series:
    _, _, hist = ind.macd(df["close"], int(fast), int(slow), int(signal))
    return (hist > 0).astype(float).fillna(0.0)


def _rsi_reversion(df: pd.DataFrame, period: int = 14,
                   buy_below: float = 30, exit_above: float = 55, **_) -> pd.Series:
    """Buy when RSI dips below ``buy_below``; hold until it recovers past ``exit_above``."""
    rsi = ind.rsi(df["close"], int(period))
    pos = []
    holding = 0.0
    for r in rsi:
        if r != r:  # NaN warm-up
            pos.append(0.0)
            continue
        if holding == 0.0 and r < buy_below:
            holding = 1.0
        elif holding == 1.0 and r > exit_above:
            holding = 0.0
        pos.append(holding)
    return pd.Series(pos, index=df.index)


@dataclass
class Strategy:
    name: str
    fn: Callable[..., pd.Series]
    label: str
    description: str
    defaults: dict = field(default_factory=dict)

    def signal(self, df: pd.DataFrame, params: dict | None = None) -> pd.Series:
        merged = {**self.defaults, **(params or {})}
        return self.fn(df, **merged)


REGISTRY: dict[str, Strategy] = {
    "buy_hold": Strategy(
        "buy_hold", _buy_hold, "Buy & Hold",
        "Buys on day one and never sells — the baseline every strategy is measured against.",
        {}),
    "sma_cross": Strategy(
        "sma_cross", _sma_cross, "SMA Crossover",
        "Goes long when a fast simple moving average crosses above a slow one (trend following); flat otherwise.",
        {"fast": 20, "slow": 50}),
    "ema_cross": Strategy(
        "ema_cross", _ema_cross, "EMA Crossover",
        "Like the SMA crossover but with exponential moving averages (react faster to recent price).",
        {"fast": 12, "slow": 26}),
    "price_above_sma": Strategy(
        "price_above_sma", _price_above_sma, "Price vs SMA",
        "Holds only while price is above a long moving average (a simple regime filter).",
        {"period": 200}),
    "macd": Strategy(
        "macd", _macd, "MACD Momentum",
        "Long while the MACD histogram is positive (momentum building); flat when it turns negative.",
        {"fast": 12, "slow": 26, "signal": 9}),
    "rsi_reversion": Strategy(
        "rsi_reversion", _rsi_reversion, "RSI Mean-Reversion",
        "Buys oversold dips (RSI below a threshold) and exits once RSI recovers (mean reversion).",
        {"period": 14, "buy_below": 30, "exit_above": 55}),
}


def get_strategy(name: str) -> Strategy | None:
    return REGISTRY.get(str(name).lower().strip())


def list_strategies() -> list[dict]:
    return [{"name": s.name, "label": s.label, "description": s.description,
             "defaults": s.defaults} for s in REGISTRY.values()]
