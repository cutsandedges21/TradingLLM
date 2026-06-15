"""Performance metrics for a backtest run — the numbers a trader actually reads."""
from __future__ import annotations

import math

import pandas as pd

from trading_llm.backtest.engine import RunResult, Trade


def _total_return(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] == 0:
        return 0.0
    return float(equity.iloc[-1] / equity.iloc[0] - 1)


def _max_drawdown(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    dd = equity / equity.cummax() - 1.0
    return float(dd.min())


def _sharpe(returns: pd.Series, ppy: int) -> float:
    sd = float(returns.std())
    if sd == 0 or math.isnan(sd):
        return 0.0
    return float(returns.mean() / sd * math.sqrt(ppy))


def _cagr(equity: pd.Series, ppy: int) -> float:
    n = len(equity)
    if n < 2 or equity.iloc[0] <= 0:
        return 0.0
    years = n / ppy
    if years <= 0:
        return 0.0
    growth = equity.iloc[-1] / equity.iloc[0]
    if growth <= 0:
        return -1.0
    return float(growth ** (1 / years) - 1)


def _win_rate(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.return_pct > 0)
    return round(wins / len(trades) * 100, 1)


def compute(result: RunResult, ppy: int = 252) -> dict:
    eq, bench = result.equity, result.benchmark
    strat_tr = _total_return(eq)
    bench_tr = _total_return(bench)
    return {
        "total_return_pct": round(strat_tr * 100, 2),
        "buy_hold_return_pct": round(bench_tr * 100, 2),
        "excess_return_pct": round((strat_tr - bench_tr) * 100, 2),
        "cagr_pct": round(_cagr(eq, ppy) * 100, 2),
        "max_drawdown_pct": round(_max_drawdown(eq) * 100, 2),
        "buy_hold_max_drawdown_pct": round(_max_drawdown(bench) * 100, 2),
        "sharpe": round(_sharpe(result.net_returns, ppy), 2),
        "volatility_pct": round(float(result.net_returns.std()) * math.sqrt(ppy) * 100, 2),
        "exposure_pct": round(float(result.positions.mean()) * 100, 1),
        "n_trades": len(result.trades),
        "win_rate_pct": _win_rate(result.trades),
        "final_equity": round(float(eq.iloc[-1]), 2) if len(eq) else None,
        "start_equity": round(float(eq.iloc[0]), 2) if len(eq) else None,
    }
