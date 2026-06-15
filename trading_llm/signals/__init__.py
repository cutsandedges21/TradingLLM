"""Smart-money signals + market regime (Phase A).

Surfaces what large institutions (13F) and corporate insiders (Form 4) are doing,
plus the current market regime, as *context* for the copilot and a UI panel.
Honest framing: these are public, lagged signals — informative, not a guaranteed
edge. Backtesting (Phase B) and acting/learning (Phase C) build on this.
"""
from __future__ import annotations

from trading_llm.signals.models import (
    Signal, SignalBundle, Regime,
    INSIDER_BUY, INSIDER_SELL, INST_13F, CONGRESS,
)
from trading_llm.signals.regime import detect_regime
from trading_llm.signals.service import SignalService
from trading_llm.signals import format as signal_format

__all__ = [
    "Signal", "SignalBundle", "Regime", "SignalService", "detect_regime",
    "signal_format", "INSIDER_BUY", "INSIDER_SELL", "INST_13F", "CONGRESS",
]
