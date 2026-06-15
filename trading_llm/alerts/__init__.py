"""Strategy automation + alerts (Phase D4).

Turn signals into mechanical discipline: standing rules (AND-conditions over
per-symbol features) that fire alerts with pre-sized paper proposals, plus an
honest walk-forward backtest of the price-computable conditions. The smart-money
conditions have no point-in-time history, so they're forward-only — tracked by
the learning loop, never pseudo-backtested.
"""
from __future__ import annotations

from trading_llm.alerts import rules, store, walkforward

__all__ = ["rules", "store", "walkforward"]
