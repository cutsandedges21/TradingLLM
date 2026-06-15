"""Market-regime detector — computed entirely from price bars we already fetch.

No new data source: it reuses ``MarketData.get_bars`` for SPY (trend / volatility /
momentum) and the factor universe (breadth). The classification is a deterministic
function of the bars, so the pure helpers below are unit-testable with synthetic
series. Thresholds live as module constants so a test can pin the boundaries.
"""
from __future__ import annotations

from datetime import datetime

from trading_llm.signals.models import Regime
from trading_llm.factors.runner import DEFAULT_UNIVERSE, clean_universe

# --- classification thresholds (documented + tunable) ---
TREND_BAND_PCT = 1.0       # |SPY vs 200dma| within this = "sideways"
VOL_LOW_MAX = 12.0         # annualized realized vol (%) below = "low"
VOL_HIGH_MIN = 22.0        # above = "high"; between = "normal"
BREADTH_STRONG = 55.0      # % of universe above 50dma for risk-on
BREADTH_WEAK = 35.0        # at/below for risk-off
TRADING_DAYS = 252


def sma(closes: list[float], window: int) -> float | None:
    if len(closes) < window or window <= 0:
        return None
    return sum(closes[-window:]) / window


def pct_vs_sma(closes: list[float], window: int) -> float | None:
    s = sma(closes, window)
    if s is None or s == 0 or not closes:
        return None
    return (closes[-1] / s - 1.0) * 100.0


def realized_vol(closes: list[float], window: int = 20) -> float | None:
    """Annualized realized volatility (%) from daily simple returns."""
    if len(closes) < window + 1:
        return None
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(len(closes) - window, len(closes))
            if closes[i - 1]]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return (var ** 0.5) * (TRADING_DAYS ** 0.5) * 100.0


def momentum_pct(closes: list[float], window: int = 63) -> float | None:
    if len(closes) < window + 1 or not closes[-window - 1]:
        return None
    return (closes[-1] / closes[-window - 1] - 1.0) * 100.0


def classify_trend(spy_vs_200: float | None) -> str:
    if spy_vs_200 is None:
        return "unknown"
    if spy_vs_200 > TREND_BAND_PCT:
        return "up"
    if spy_vs_200 < -TREND_BAND_PCT:
        return "down"
    return "sideways"


def classify_vol(rv: float | None) -> str:
    if rv is None:
        return "unknown"
    if rv < VOL_LOW_MAX:
        return "low"
    if rv > VOL_HIGH_MIN:
        return "high"
    return "normal"


def classify_label(trend: str, breadth_pct: float, vol: str, momentum: float | None) -> str:
    """Deterministic risk-on / neutral / risk-off label."""
    mom = momentum if momentum is not None else 0.0
    if trend == "down" or breadth_pct <= BREADTH_WEAK or (vol == "high" and mom < 0):
        return "risk_off"
    if trend == "up" and breadth_pct >= BREADTH_STRONG and vol != "high":
        return "risk_on"
    return "neutral"


def _summary(r: Regime) -> str:
    nice = {"risk_on": "RISK-ON", "neutral": "NEUTRAL", "risk_off": "RISK-OFF"}.get(r.label, "UNKNOWN")
    return (f"{nice} — trend {r.trend} ({r.spy_vs_200dma_pct:+.1f}% vs 200dma) · "
            f"breadth {r.breadth_pct:.0f}% above 50dma · vol {r.vol} "
            f"({r.realized_vol_20d:.0f}%) · 3-mo momentum {r.momentum_3m_pct:+.1f}%")


def compute_breadth(data, universe: list[str]) -> float:
    """% of universe trading above its own 50-day SMA. 0.0 if no data."""
    uni = clean_universe(universe)
    above = total = 0
    for sym in uni:
        closes = data.get_bars(sym, "1Day", 60)
        s = sma(closes, 50)
        if s is None:
            continue
        total += 1
        if closes[-1] > s:
            above += 1
    return (above / total * 100.0) if total else 0.0


def detect_regime(data, universe: list[str] | None = None, market_symbol: str = "SPY") -> Regime:
    """Assemble the market regime from live bars. Fail-soft: returns ok=False
    (so the snapshot simply omits the regime line) when SPY bars are unavailable."""
    spy = data.get_bars(market_symbol, "1Day", 260)
    if len(spy) < 200:
        return Regime(ok=False, summary="Regime unavailable (insufficient market data).",
                      as_of=datetime.now().strftime("%Y-%m-%d"))

    spy_vs_200 = pct_vs_sma(spy, 200) or 0.0
    rv = realized_vol(spy, 20)
    mom = momentum_pct(spy, 63)
    breadth = compute_breadth(data, universe or DEFAULT_UNIVERSE)

    trend = classify_trend(spy_vs_200)
    vol = classify_vol(rv)
    label = classify_label(trend, breadth, vol, mom)

    r = Regime(
        ok=True, label=label, trend=trend, vol=vol, breadth_pct=breadth,
        spy_vs_200dma_pct=spy_vs_200, realized_vol_20d=rv or 0.0,
        momentum_3m_pct=mom or 0.0, as_of=datetime.now().strftime("%Y-%m-%d"),
    )
    r.summary = _summary(r)
    return r
