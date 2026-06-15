"""Options flow — put/call ratios, ATM implied vol, and unusual options activity.

Free (delayed) via yfinance option chains. Put/call ratios gauge positioning/fear
(often read contrarian); a volume spike far above open interest flags fresh
"unusual" bets. The summary math is pure + testable; the fetch is fail-soft
(option chains are the flakiest free endpoint).
"""
from __future__ import annotations

from statistics import mean

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None  # type: ignore


def _num(x) -> float:
    try:
        v = float(x)
        return v if v == v else 0.0  # drop NaN
    except Exception:
        return 0.0


def summarize_chain(calls: list[dict], puts: list[dict], spot: float) -> dict:
    """Pure summary of one or more option chains for a name."""
    call_vol = sum(_num(c.get("volume")) for c in calls)
    put_vol = sum(_num(p.get("volume")) for p in puts)
    call_oi = sum(_num(c.get("openInterest")) for c in calls)
    put_oi = sum(_num(p.get("openInterest")) for p in puts)

    pcr_vol = round(put_vol / call_vol, 2) if call_vol else None
    pcr_oi = round(put_oi / call_oi, 2) if call_oi else None

    # ATM IV: average the implied vols of the call+put nearest the spot.
    atm_iv = None
    if spot and (calls or puts):
        def nearest_iv(rows):
            cand = [(abs(_num(r.get("strike")) - spot), _num(r.get("impliedVolatility")))
                    for r in rows if _num(r.get("strike")) > 0 and _num(r.get("impliedVolatility")) > 0]
            return min(cand)[1] if cand else None
        ivs = [v for v in (nearest_iv(calls), nearest_iv(puts)) if v]
        if ivs:
            atm_iv = round(mean(ivs) * 100, 1)

    # Unusual: volume well above existing open interest (fresh positioning).
    unusual = []
    for side, rows in (("call", calls), ("put", puts)):
        for r in rows:
            vol = _num(r.get("volume"))
            oi = _num(r.get("openInterest"))
            if vol >= 200 and vol > 3 * max(oi, 1):
                unusual.append({
                    "side": side, "strike": round(_num(r.get("strike")), 2),
                    "volume": int(vol), "open_interest": int(oi),
                    "vol_oi_ratio": round(vol / max(oi, 1), 1),
                    "last": round(_num(r.get("lastPrice")), 2),
                })
    unusual.sort(key=lambda x: x["volume"], reverse=True)

    if pcr_vol is None:
        sentiment = "no flow"
    elif pcr_vol < 0.7:
        sentiment = "call-heavy (bullish positioning / possible greed)"
    elif pcr_vol > 1.1:
        sentiment = "put-heavy (bearish/hedging / possible fear)"
    else:
        sentiment = "balanced"

    return {
        "put_call_volume_ratio": pcr_vol,
        "put_call_oi_ratio": pcr_oi,
        "atm_iv_pct": atm_iv,
        "total_call_volume": int(call_vol),
        "total_put_volume": int(put_vol),
        "unusual": unusual[:6],
        "sentiment": sentiment,
    }


def fetch(symbol: str, spot: float | None = None, max_expiries: int = 2) -> dict:
    """Fetch + summarize the nearest expiries' option chains. Fail-soft → ok False."""
    if yf is None:
        return {"ok": False, "reason": "yfinance unavailable."}
    try:
        t = yf.Ticker(symbol.replace("/", "-"))
        expiries = list(t.options or [])[:max_expiries]
        if not expiries:
            return {"ok": False, "reason": "No listed options for this symbol."}
        if spot is None:
            fi = t.fast_info
            spot = float(getattr(fi, "last_price", 0) or (fi["last_price"] if hasattr(fi, "__getitem__") else 0) or 0)
        calls, puts = [], []
        for exp in expiries:
            ch = t.option_chain(exp)
            calls += ch.calls.to_dict("records")
            puts += ch.puts.to_dict("records")
    except Exception:
        return {"ok": False, "reason": "Could not fetch option chains (free options data is flaky)."}

    summary = summarize_chain(calls, puts, spot or 0.0)
    summary.update({"ok": True, "symbol": symbol.upper(), "expiries": expiries,
                    "spot": round(spot or 0.0, 2),
                    "note": "Delayed, free options data. Put/call is often read contrarian — context, not a signal."})
    return summary
