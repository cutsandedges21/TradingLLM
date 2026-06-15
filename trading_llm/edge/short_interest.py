"""Short interest & squeeze setups — free via yfinance fundamentals.

High short-percent-of-float + many days-to-cover = fuel for a short squeeze (a
sharp rally as shorts are forced to buy back). It's lagged (FINRA reports
bi-monthly) and crowded-ish, but still a genuine, free risk/opportunity flag.
The scoring is pure + testable; the fetch is fail-soft.
"""
from __future__ import annotations

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None  # type: ignore


def squeeze_score(short_pct_float: float | None, days_to_cover: float | None) -> int | None:
    """0–100 squeeze-potential score. ~40%+ short float and ~10+ days-to-cover are extreme."""
    if short_pct_float is None and days_to_cover is None:
        return None
    spf = short_pct_float or 0.0
    dtc = days_to_cover or 0.0
    s = min(spf, 40.0) / 40.0 * 60.0      # up to 60 pts from short % of float
    d = min(dtc, 10.0) / 10.0 * 40.0      # up to 40 pts from days-to-cover
    return round(s + d)


def _label(score: int | None) -> str:
    if score is None:
        return "no data"
    if score >= 60:
        return "high squeeze potential"
    if score >= 35:
        return "elevated"
    return "low"


def fetch(symbol: str) -> dict:
    """Short-interest snapshot for a symbol. Fail-soft → ok False."""
    if yf is None:
        return {"ok": False, "reason": "yfinance unavailable."}
    try:
        info = yf.Ticker(symbol.replace("/", "-")).get_info()
    except Exception:
        try:
            info = yf.Ticker(symbol.replace("/", "-")).info
        except Exception:
            return {"ok": False, "reason": "Could not fetch short-interest data."}
    if not isinstance(info, dict):
        return {"ok": False, "reason": "No fundamentals available."}

    spf_raw = info.get("shortPercentOfFloat")          # fraction, e.g. 0.05
    short_pct = round(spf_raw * 100, 2) if isinstance(spf_raw, (int, float)) else None
    dtc = info.get("shortRatio")                        # days to cover
    shares_short = info.get("sharesShort")
    prior = info.get("sharesShortPriorMonth")
    change_pct = None
    if isinstance(shares_short, (int, float)) and isinstance(prior, (int, float)) and prior:
        change_pct = round((shares_short / prior - 1) * 100, 1)

    score = squeeze_score(short_pct, dtc if isinstance(dtc, (int, float)) else None)
    if short_pct is None and shares_short is None:
        return {"ok": False, "reason": "No short-interest data for this name (common for ETFs/large caps)."}
    return {
        "ok": True,
        "symbol": symbol.upper(),
        "short_pct_float": short_pct,
        "days_to_cover": round(dtc, 1) if isinstance(dtc, (int, float)) else None,
        "shares_short": shares_short,
        "shares_short_prior": prior,
        "change_pct": change_pct,
        "squeeze_score": score,
        "label": _label(score),
        "note": "Short interest is lagged (bi-monthly FINRA reporting). High score = squeeze fuel, not a buy.",
    }
