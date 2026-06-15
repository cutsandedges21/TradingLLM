"""Historical OHLC loader for backtests (free, via yfinance).

Returns a tidy pandas DataFrame indexed by date with lowercase
open/high/low/close/volume columns. Guarded import so the package loads even
when yfinance is absent (a backtest just reports data unavailable).
"""
from __future__ import annotations

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None  # type: ignore

from trading_llm.market.data import to_yf

# Friendly period/interval validation. Daily is the default and most robust.
VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max", "ytd"}
VALID_INTERVALS = {"1d", "1wk", "1mo", "1h"}

# bars per year, for annualizing metrics
PERIODS_PER_YEAR = {"1d": 252, "1wk": 52, "1mo": 12, "1h": 1638}


def load_ohlc(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame | None:
    """Load OHLC bars for ``symbol``. Returns None if unavailable."""
    if yf is None:
        return None
    period = period if period in VALID_PERIODS else "2y"
    interval = interval if interval in VALID_INTERVALS else "1d"
    try:
        df = yf.Ticker(to_yf(symbol)).history(period=period, interval=interval, auto_adjust=True)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df = df[cols].dropna(subset=["close"])
    return df if len(df) >= 2 else None
