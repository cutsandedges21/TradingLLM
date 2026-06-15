"""5-tier rating vocabulary + a deterministic parser, and rating -> trade mapping.

Rating scale (most bullish to most bearish): Buy, Overweight, Hold, Underweight, Sell.
Ported from TradingAgents' rating heuristic; the trade mapping is ours (it targets
the local paper broker and respects the configured per-trade risk budget).
"""
from __future__ import annotations

import re

RATINGS_5_TIER = ("Buy", "Overweight", "Hold", "Underweight", "Sell")
_RATING_SET = {r.lower() for r in RATINGS_5_TIER}

# Matches "Rating: X" / "rating - X" / "Rating: **X**".
_RATING_LABEL_RE = re.compile(r"rating.*?[:\-][\s*]*(\w+)", re.IGNORECASE)

_BUY_SIDE = {"buy", "overweight"}
_SELL_SIDE = {"sell", "underweight"}


def parse_rating(text: str, default: str = "Hold") -> str:
    """Heuristically extract a 5-tier rating from prose (label first, then any word)."""
    for line in text.splitlines():
        m = _RATING_LABEL_RE.search(line)
        if m and m.group(1).lower() in _RATING_SET:
            return m.group(1).capitalize()
    for line in text.splitlines():
        for word in line.lower().split():
            clean = word.strip("*:.,")
            if clean in _RATING_SET:
                return clean.capitalize()
    return default


def rating_to_proposal(rating: str, ticker: str, max_position_usd: float,
                       rationale: str = "") -> dict | None:
    """Map a 5-tier rating to a paper-trade proposal, or None for Hold.

    Sizes the order at the configured per-trade budget (``max_position_usd``) so it
    passes the risk gate; the user still confirms and can change the size.
    """
    r = rating.lower()
    if r in _BUY_SIDE:
        action = "buy"
    elif r in _SELL_SIDE:
        action = "sell"
    else:
        return None
    return {
        "action": action,
        "symbol": ticker.upper(),
        "qty": None,
        "notional": float(max_position_usd),
        "order_type": "market",
        "limit_price": None,
        "rationale": (rationale or f"Multi-agent committee rated {rating}.")[:200],
    }
