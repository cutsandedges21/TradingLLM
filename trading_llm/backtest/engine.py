"""Bar-by-bar backtest execution.

Next-bar semantics: a target position derived from data up to and including bar
*t* is acted on at bar *t+1* (signal shifted by one) to avoid look-ahead. Trades
incur a round-trip cost in basis points on turnover. Long/flat only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Trade:
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    return_pct: float


@dataclass
class RunResult:
    equity: pd.Series          # strategy equity curve
    benchmark: pd.Series       # buy & hold equity curve
    net_returns: pd.Series     # per-bar strategy returns (after costs)
    positions: pd.Series       # realized positions (shifted)
    trades: list = field(default_factory=list)


def run(df: pd.DataFrame, signal: pd.Series, initial: float = 10_000.0,
        cost_bps: float = 5.0) -> RunResult:
    """Simulate ``signal`` over ``df``; return equity curves, returns, and trades."""
    close = df["close"].astype(float)
    bar_ret = close.pct_change().fillna(0.0)

    # Act on the prior bar's signal (no look-ahead).
    positions = signal.reindex(df.index).fillna(0.0).clip(0.0, 1.0).shift(1).fillna(0.0)

    # Cost charged on turnover (change in position) in basis points.
    turnover = positions.diff().abs().fillna(positions.abs())
    cost = turnover * (cost_bps / 10_000.0)

    net = positions * bar_ret - cost
    equity = initial * (1.0 + net).cumprod()
    benchmark = initial * (1.0 + bar_ret).cumprod()

    trades = _extract_trades(close, positions)
    return RunResult(equity=equity, benchmark=benchmark, net_returns=net,
                     positions=positions, trades=trades)


def _extract_trades(close: pd.Series, positions: pd.Series) -> list[Trade]:
    """Pair each entry (0 -> long) with its exit (long -> 0) into closed trades."""
    trades: list[Trade] = []
    in_pos = False
    entry_i = 0
    idx = list(positions.index)
    pv = positions.values
    for i in range(len(pv)):
        if not in_pos and pv[i] > 0:
            in_pos, entry_i = True, i
        elif in_pos and pv[i] == 0:
            ep, xp = float(close.iloc[entry_i]), float(close.iloc[i])
            trades.append(Trade(
                entry_date=str(idx[entry_i])[:10], exit_date=str(idx[i])[:10],
                entry_price=round(ep, 4), exit_price=round(xp, 4),
                return_pct=round((xp / ep - 1) * 100, 2) if ep else 0.0))
            in_pos = False
    if in_pos:  # still open at the end -> mark to last close
        ep, xp = float(close.iloc[entry_i]), float(close.iloc[-1])
        trades.append(Trade(
            entry_date=str(idx[entry_i])[:10], exit_date=str(idx[-1])[:10] + " (open)",
            entry_price=round(ep, 4), exit_price=round(xp, 4),
            return_pct=round((xp / ep - 1) * 100, 2) if ep else 0.0))
    return trades
