"""Walk-forward backtest of a rule's *price-computable* conditions.

Honest by construction: only point-in-time fields (RSI, trend, %-vs-SMA200, MACD)
are reconstructed historically; smart-money conditions are skipped + reported as
forward-only. Entry dates are the rising edges where the price conditions first
hold; we then reuse the event-study engine (with its in/out-of-sample split) to
measure forward returns + alpha + edge over the rule's holding period.
"""
from __future__ import annotations

from trading_llm.signals import eventstudy
from trading_llm.alerts.rules import evaluate_conditions

BACKTEST_FIELDS = {"rsi", "trend", "price_vs_sma200_pct", "macd"}


def _sma(closes: list[float], w: int) -> list:
    out = [None] * len(closes)
    s = 0.0
    for i, c in enumerate(closes):
        s += c
        if i >= w:
            s -= closes[i - w]
        if i >= w - 1:
            out[i] = s / w
    return out


def _rsi(closes: list[float], period: int = 14) -> list:
    out = [None] * len(closes)
    if len(closes) <= period:
        return out
    ag = al = 0.0
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0.0), max(-ch, 0.0)
        if i <= period:
            ag += g; al += l
            if i == period:
                ag /= period; al /= period
                out[i] = 100.0 - 100.0 / (1 + (ag / al if al else 999))
        else:
            ag = (ag * (period - 1) + g) / period
            al = (al * (period - 1) + l) / period
            out[i] = 100.0 - 100.0 / (1 + (ag / al if al else 999))
    return out


def _ema(closes: list[float], span: int) -> list:
    out = [None] * len(closes)
    k = 2.0 / (span + 1)
    e = None
    for i, c in enumerate(closes):
        e = c if e is None else (c - e) * k + e
        out[i] = e
    return out


def _macd_hist(closes: list[float]) -> list:
    e12, e26 = _ema(closes, 12), _ema(closes, 26)
    macd = [(a - b) if (a is not None and b is not None) else None for a, b in zip(e12, e26)]
    sig = _ema([m if m is not None else 0.0 for m in macd], 9)
    return [(m - s) if (m is not None and s is not None) else None for m, s in zip(macd, sig)]


def _features_at(i, closes, sma20, sma50, sma200, rsi, hist) -> dict:
    f: dict = {}
    if rsi[i] is not None:
        f["rsi"] = rsi[i]
    if sma20[i] is not None and sma50[i] is not None:
        f["trend"] = "up" if sma20[i] > sma50[i] else "down" if sma20[i] < sma50[i] else "sideways"
    if sma200[i]:
        f["price_vs_sma200_pct"] = (closes[i] / sma200[i] - 1) * 100
    if hist[i] is not None:
        f["macd"] = "bullish" if hist[i] > 0 else "bearish" if hist[i] < 0 else "flat"
    return f


def backtest(rule: dict, dates: list, closes: list[float],
             spy_dates: list, spy_closes: list[float]) -> dict:
    """Walk-forward the rule's price conditions; return event-study stats over hold_days."""
    all_conds = rule.get("conditions", [])
    conds = [c for c in all_conds if c.get("field") in BACKTEST_FIELDS]
    skipped = sorted({c.get("field") for c in all_conds if c.get("field") not in BACKTEST_FIELDS})
    if not conds:
        return {"ok": False, "skipped_forward_only": skipped,
                "reason": "This rule relies only on smart-money signals (no point-in-time history) — "
                          "it can't be backtested; track it forward via the learning loop instead."}
    if len(closes) < 220:
        return {"ok": False, "reason": "Not enough price history to backtest."}

    sma20, sma50, sma200 = _sma(closes, 20), _sma(closes, 50), _sma(closes, 200)
    rsi, hist = _rsi(closes), _macd_hist(closes)

    entries, prev = [], False
    for i in range(len(closes)):
        f = _features_at(i, closes, sma20, sma50, sma200, rsi, hist)
        cur = evaluate_conditions(conds, f)
        if cur and not prev:
            entries.append({"date": str(dates[i])})
        prev = cur

    hold = int(rule.get("hold_days", 20))
    res = eventstudy.event_study(entries, dates, closes, spy_dates, spy_closes, horizons=(hold,))
    res["n_entries"] = len(entries)
    res["hold_days"] = hold
    res["skipped_forward_only"] = skipped
    res["backtested_conditions"] = [c.get("field") for c in conds]
    return res
