"""Post-earnings announcement drift (PEAD) — a long-documented anomaly.

Stocks that gap *up* on earnings tend to keep drifting up for weeks (and down for
down-gaps) as the market under-reacts. We proxy the "surprise" with the 1-day price
reaction (free; no estimate data needed), then measure the forward drift — and
report whether THIS name has historically drifted after a strong reaction.
Pure core is testable; the earnings-date fetch is fail-soft.
"""
from __future__ import annotations

import bisect
from datetime import datetime
from statistics import mean

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None  # type: ignore


def earnings_reactions(earn_dates: list, dates: list, closes: list[float],
                       drift_days: int = 20) -> list[dict]:
    """For each earnings date: the 1-day reaction and the subsequent ``drift_days`` drift."""
    out = []
    for e in earn_dates:
        i_after = bisect.bisect_left(dates, e)
        if i_after <= 0 or i_after >= len(dates):
            continue
        i_before = i_after - 1
        if not closes[i_before]:
            continue
        reaction = closes[i_after] / closes[i_before] - 1.0
        drift = None
        j = i_after + drift_days
        if j < len(dates) and closes[i_after]:
            drift = closes[j] / closes[i_after] - 1.0
        out.append({"date": str(e)[:10], "reaction_pct": round(reaction * 100, 2),
                    "drift_pct": round(drift * 100, 2) if drift is not None else None})
    return out


def summarize_pead(reactions: list[dict], threshold: float = 2.0) -> dict:
    """Average forward drift after positive- vs negative-reaction earnings."""
    pos = [r["drift_pct"] for r in reactions
           if r["drift_pct"] is not None and r["reaction_pct"] >= threshold]
    neg = [r["drift_pct"] for r in reactions
           if r["drift_pct"] is not None and r["reaction_pct"] <= -threshold]
    pos_drift = round(mean(pos), 2) if pos else None
    neg_drift = round(mean(neg), 2) if neg else None
    has_pead = pos_drift is not None and neg_drift is not None and pos_drift > neg_drift
    return {
        "pos_reaction_avg_drift_pct": pos_drift, "n_pos": len(pos),
        "neg_reaction_avg_drift_pct": neg_drift, "n_neg": len(neg),
        "has_pead": has_pead,
    }


def analyze(symbol: str, data, drift_days: int = 20) -> dict:
    """Fetch earnings dates + prices and build the PEAD profile. Fail-soft → ok False."""
    if yf is None:
        return {"ok": False, "reason": "yfinance unavailable."}
    # earnings dates (past only)
    earn = []
    try:
        df = yf.Ticker(symbol.replace("/", "-")).get_earnings_dates(limit=20)
        today = datetime.now().date()
        for idx in (df.index if df is not None else []):
            try:
                d = idx.date()
            except Exception:
                continue
            if d <= today:
                earn.append(d)
    except Exception:
        earn = []
    if len(earn) < 4:
        return {"ok": False, "reason": "Not enough earnings history for a PEAD read."}

    try:
        candles = data.get_ohlc(symbol, "3y", "1d", 1000)  # full 3y (default limit caps at 400)
        dates = [datetime.strptime(str(c["time"])[:10], "%Y-%m-%d").date() for c in candles]
        closes = [float(c["close"]) for c in candles]
    except Exception:
        return {"ok": False, "reason": "Price history unavailable."}
    if len(dates) < drift_days + 5:
        return {"ok": False, "reason": "Price history too short."}

    earn = sorted(earn)
    reactions = earnings_reactions(earn, dates, closes, drift_days)
    if not reactions:
        return {"ok": False, "reason": "Could not align earnings dates with prices."}
    summary = summarize_pead(reactions)
    last = reactions[-1]
    drift_word = "up" if (summary["has_pead"]) else "mixed"
    return {
        "ok": True, "symbol": symbol.upper(), "drift_days": drift_days,
        "last_earnings": last["date"], "last_reaction_pct": last["reaction_pct"],
        "last_drift_pct": last["drift_pct"],
        "n_events": len(reactions),
        **summary,
        "verdict": (f"After a strong earnings pop, {symbol.upper()} historically drifted "
                    f"{summary['pos_reaction_avg_drift_pct']:+.1f}% over {drift_days}d "
                    f"(n={summary['n_pos']}) vs {summary['neg_reaction_avg_drift_pct']:+.1f}% after a drop "
                    f"(n={summary['n_neg']})." if summary["has_pead"]
                    else f"No clear post-earnings drift edge for {symbol.upper()} in the available history."),
        "recent": reactions[-6:],
        "note": "Reaction proxies the surprise (no free estimate data). Small samples — weak evidence.",
    }
