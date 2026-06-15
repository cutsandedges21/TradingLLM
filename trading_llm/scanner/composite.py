"""Composite scoring — blend raw per-symbol readings into one transparent score.

Each component is normalized to a signal in [-1, +1] (or [0, 1] for positive-only
tilts), then weighted. Weights are renormalized over whatever components are
available, so a missing source degrades gracefully instead of zeroing the score.
Output carries the full breakdown (signal · weight · point contribution) so the
ranking is explainable. Pure — no I/O.
"""
from __future__ import annotations

import math

# Relative importance of each component (renormalized over those present).
WEIGHTS = {
    "momentum": 0.35,
    "insider": 0.30,
    "seasonality": 0.15,
    "funds": 0.10,
    "squeeze": 0.10,
}

LABELS = {
    "momentum": "Technical momentum",
    "insider": "Insider net buying (30d)",
    "seasonality": "Seasonality (this month)",
    "funds": "Institutional ownership (13F)",
    "squeeze": "Short-squeeze fuel",
}


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _momentum_signal(raw: dict):
    """Blend trend + RSI + MACD + price-vs-SMA50 into [-1, 1]. None if no data."""
    parts = []
    trend = raw.get("trend")
    if trend in ("up", "down", "sideways"):
        parts.append(1.0 if trend == "up" else -1.0 if trend == "down" else 0.0)
    rsi = raw.get("rsi")
    if isinstance(rsi, (int, float)):
        parts.append(_clamp((rsi - 50) / 20.0))      # 30→-1, 70→+1
    mom = raw.get("momentum")
    if mom in ("bullish", "bearish"):
        parts.append(1.0 if mom == "bullish" else -1.0)
    pvs = raw.get("price_vs_sma50_pct")
    if isinstance(pvs, (int, float)):
        parts.append(_clamp(pvs / 10.0))             # ±10% vs SMA50 → ±1
    return sum(parts) / len(parts) if parts else None


def _component_signals(raw: dict) -> dict:
    """Map raw readings to normalized signals; omit components with no data."""
    sig: dict[str, float] = {}

    m = _momentum_signal(raw)
    if m is not None:
        sig["momentum"] = round(m, 3)

    net = raw.get("net_insider_30d")
    if isinstance(net, (int, float)) and net != 0:
        sig["insider"] = round(math.tanh(net / 5_000_000.0), 3)   # ±$5M → ~±0.76

    sea = raw.get("seasonality_month_pct")
    if isinstance(sea, (int, float)):
        sig["seasonality"] = round(_clamp(sea / 3.0), 3)          # ±3%/mo → ±1

    funds = raw.get("funds_holding")
    if isinstance(funds, (int, float)) and funds > 0:
        sig["funds"] = round(min(funds / 4.0, 1.0), 3)            # positive-only tilt

    sq = raw.get("squeeze_score")
    if isinstance(sq, (int, float)) and sq > 0:
        sig["squeeze"] = round(min(sq / 100.0, 1.0), 3)          # positive-only tilt

    return sig


def score_symbol(raw: dict) -> dict:
    """Composite 0–100 score (50 = neutral) with a transparent breakdown."""
    signals = _component_signals(raw)
    present = [k for k in WEIGHTS if k in signals]
    wsum = sum(WEIGHTS[k] for k in present)
    if not present or wsum == 0:
        return {"score": 50.0, "signal": 0.0, "direction": "neutral",
                "components": [], "available": [], "n_components": 0}

    composite = sum(WEIGHTS[k] * signals[k] for k in present) / wsum
    score = round(50 + 50 * composite, 1)
    components = [{
        "name": k, "label": LABELS[k], "signal": signals[k],
        "weight": round(WEIGHTS[k] / wsum, 3),
        "points": round(50 * WEIGHTS[k] * signals[k] / wsum, 1),
    } for k in sorted(present, key=lambda x: abs(WEIGHTS[x] * signals[x]), reverse=True)]

    direction = "bullish" if score >= 58 else "bearish" if score <= 42 else "neutral"
    return {"score": score, "signal": round(composite, 3), "direction": direction,
            "components": components, "available": present, "n_components": len(present)}
