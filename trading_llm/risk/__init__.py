"""Risk & position-sizing engine (Phase D1).

The biggest *real* edge for a retail account isn't a secret signal — it's not
blowing up. This package turns that into math: position sizing, portfolio heat,
risk-of-ruin, and a pre-trade checklist that runs before every confirmation.
Pure functions, no I/O — fully testable offline.
"""
from __future__ import annotations

from trading_llm.risk.sizing import (
    fixed_fractional_size, atr_from_bars, kelly_fraction, suggested_risk_pct,
    risk_of_ruin, portfolio_heat, pretrade_check, expectancy,
)

__all__ = [
    "fixed_fractional_size", "atr_from_bars", "kelly_fraction", "suggested_risk_pct",
    "risk_of_ruin", "portfolio_heat", "pretrade_check", "expectancy",
]
