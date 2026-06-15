"""Phase 2 — backtesting (educational, free data).

A bar-by-bar long/flat backtest engine over free yfinance history, a registry of
beginner-legible built-in strategies, trader-grade metrics (return, CAGR,
drawdown, Sharpe, win rate vs buy & hold), and a plain-English explainer.

    from trading_llm.backtest import backtest, explain, list_strategies
    result = backtest("AAPL", "sma_cross", {"fast": 20, "slow": 50}, period="2y")
    print(explain(result))
"""
from trading_llm.backtest.runner import backtest, BacktestResult
from trading_llm.backtest.explain import explain
from trading_llm.backtest.strategies import list_strategies, get_strategy
from trading_llm.backtest.hyperopt import optimize, explain as explain_optimize, OptimizeResult
from trading_llm.backtest.custom import run_custom
from trading_llm.backtest.dsl import validate as validate_strategy
from trading_llm.backtest.pine import to_pine

__all__ = ["backtest", "BacktestResult", "explain", "list_strategies", "get_strategy",
           "optimize", "explain_optimize", "OptimizeResult",
           "run_custom", "validate_strategy", "to_pine"]
