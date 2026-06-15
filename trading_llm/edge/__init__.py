"""Under-crowded, legal "edge" signals (Phase D2).

Lower-capacity signals big funds largely ignore — options flow, short-interest
squeezes, post-earnings drift, and seasonality — all from free data. Honest:
weak, lagged, and not guaranteed; they're context that *can* tilt odds, not a
money machine. Pure cores are unit-tested; all fetchers are fail-soft.
"""
from __future__ import annotations

from trading_llm.edge import seasonality, short_interest, options_flow, pead

__all__ = ["seasonality", "short_interest", "options_flow", "pead"]
