"""Fetch realized outcomes for a past decision (raw return + alpha vs a benchmark).

Ported from TradingAgents' ``_fetch_returns`` / ``_resolve_benchmark``. Uses
yfinance (guarded) so a past decision can be scored once enough price history
exists; returns ``(None, None, None)`` when data isn't available yet (too recent,
delisted, or offline) — the entry then stays pending until the next attempt.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None  # type: ignore

from trading_llm.market.data import is_crypto, to_yf

logger = logging.getLogger(__name__)


def resolve_benchmark(ticker: str) -> str:
    """Benchmark used as the alpha baseline. Crypto -> BTC, everything else -> SPY."""
    return "BTC-USD" if is_crypto(ticker) else "SPY"


def fetch_returns(ticker: str, trade_date: str, holding_days: int = 5,
                  benchmark: str | None = None):
    """Return (raw_return, alpha_return, actual_holding_days) or (None, None, None)."""
    if yf is None:
        return None, None, None
    benchmark = benchmark or resolve_benchmark(ticker)
    yf_ticker = to_yf(ticker)
    try:
        start = datetime.strptime(str(trade_date), "%Y-%m-%d")
        end = start + timedelta(days=holding_days + 7)  # buffer for weekends/holidays
        end_str = end.strftime("%Y-%m-%d")

        stock = yf.Ticker(yf_ticker).history(start=str(trade_date), end=end_str)
        bench = yf.Ticker(benchmark).history(start=str(trade_date), end=end_str)

        if len(stock) < 2 or len(bench) < 2:
            return None, None, None

        actual_days = min(holding_days, len(stock) - 1, len(bench) - 1)
        raw = float((stock["Close"].iloc[actual_days] - stock["Close"].iloc[0])
                    / stock["Close"].iloc[0])
        bench_ret = float((bench["Close"].iloc[actual_days] - bench["Close"].iloc[0])
                          / bench["Close"].iloc[0])
        return raw, raw - bench_ret, actual_days
    except Exception as exc:
        logger.warning("Could not resolve outcome for %s on %s: %s", ticker, trade_date, exc)
        return None, None, None
