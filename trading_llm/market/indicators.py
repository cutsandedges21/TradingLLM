"""Local technical indicators (no external TA library, just pandas).

Everything is computed on your machine from raw price bars. These are simple,
well-known indicators — they hint at momentum and trend, they do NOT predict.
"""
from __future__ import annotations

import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(s, fast) - ema(s, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def _last(series: pd.Series):
    if series is None or len(series) == 0:
        return None
    val = series.iloc[-1]
    return None if pd.isna(val) else float(val)


def compute(closes) -> dict:
    """Return a compact indicator snapshot from a list/Series of closing prices."""
    s = pd.Series([float(c) for c in closes if c is not None], dtype="float64")
    out: dict = {
        "price": _last(s), "change_pct": None, "rsi": None, "rsi_label": None,
        "sma20": None, "sma50": None, "trend": None, "macd_hist": None, "momentum": None,
    }
    n = len(s)
    if n == 0:
        return out
    if n >= 2 and s.iloc[-2]:
        out["change_pct"] = round((s.iloc[-1] / s.iloc[-2] - 1) * 100, 2)
    if n >= 15:
        r = _last(rsi(s))
        if r is not None:
            out["rsi"] = round(r, 1)
            out["rsi_label"] = "overbought" if r >= 70 else "oversold" if r <= 30 else "neutral"
    if n >= 20:
        out["sma20"] = round(_last(sma(s, 20)) or 0, 2) or None
    if n >= 50:
        out["sma50"] = round(_last(sma(s, 50)) or 0, 2) or None
    price = out["price"]
    if price and out["sma20"] and out["sma50"]:
        if price > out["sma20"] > out["sma50"]:
            out["trend"] = "up"
        elif price < out["sma20"] < out["sma50"]:
            out["trend"] = "down"
        else:
            out["trend"] = "sideways"
    elif price and out["sma20"]:
        out["trend"] = "up" if price > out["sma20"] else "down"
    if n >= 26:
        _, _, hist = macd(s)
        h = _last(hist)
        if h is not None:
            out["macd_hist"] = round(h, 3)
            out["momentum"] = "bullish" if h > 0 else "bearish"
    return out


def summary_line(symbol: str, ind: dict) -> str:
    """One-line human/LLM readable summary for a symbol."""
    price = ind.get("price")
    if price is None:
        return f"{symbol}: no data available"
    parts = [f"{symbol} ${price:,.2f}"]
    if ind.get("change_pct") is not None:
        parts.append(f"{ind['change_pct']:+.2f}%")
    if ind.get("rsi") is not None:
        parts.append(f"RSI {ind['rsi']} ({ind['rsi_label']})")
    if ind.get("trend"):
        parts.append(f"trend {ind['trend']}")
    if ind.get("momentum"):
        parts.append(f"MACD {ind['momentum']}")
    return "  ".join(parts)
