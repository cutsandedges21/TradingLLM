"""Builds the 'current market' context the LLM reads, plus live data for the UI.

Pulls fresh prices/bars from the MarketData layer (Finnhub/yfinance/Alpaca),
computes indicators locally, and renders a compact summary. A small TTL cache
on the computed indicators keeps everything snappy.
"""
from __future__ import annotations

import time
from datetime import datetime

from trading_llm.market import indicators

_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 30  # seconds


def symbol_indicators(data, symbol: str, timeframe: str = "1Day", lookback: int = 120) -> dict:
    now = time.time()
    cached = _cache.get(symbol)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    closes = data.get_bars(symbol, timeframe, lookback)
    ind = indicators.compute(closes)

    live = data.get_price(symbol)
    if live:
        ind["price"] = round(live, 2)
        if len(closes) >= 2 and closes[-2]:
            ind["change_pct"] = round((live / closes[-2] - 1) * 100, 2)

    _cache[symbol] = (now, ind)
    return ind


def watchlist_quotes(data, symbols: list[str],
                     timeframe: str = "1Day", lookback: int = 120) -> list[dict]:
    rows = []
    for sym in symbols:
        ind = symbol_indicators(data, sym, timeframe, lookback)
        rows.append({
            "symbol": sym,
            "price": ind.get("price"),
            "change_pct": ind.get("change_pct"),
            "rsi": ind.get("rsi"),
            "trend": ind.get("trend"),
        })
    return rows


def build_snapshot(data, symbols: list[str], timeframe: str = "1Day",
                   lookback: int = 120, include_news: bool = True,
                   signal_service=None) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"[LIVE MARKET SNAPSHOT @ {stamp}]"]

    is_open = data.market_open()
    if is_open is not None:
        lines.append(f"US stock market: {'OPEN' if is_open else 'CLOSED'}")

    # Market regime (cache-only — never blocks the snapshot on a network call).
    if signal_service is not None:
        try:
            from trading_llm.signals import signal_format
            reg = signal_format.regime_summary(signal_service.cached_regime())
            if reg:
                lines.append(f"[MARKET REGIME] {reg}")
        except Exception:
            pass

    lines.append("Watchlist (price / day% / indicators):")
    for sym in symbols:
        ind = symbol_indicators(data, sym, timeframe, lookback)
        line = "  " + indicators.summary_line(sym, ind)
        if signal_service is not None:
            try:
                from trading_llm.signals import signal_format
                tag = signal_format.signals_summary(signal_service.cached_bundle(sym))
                if tag:
                    line += f"\n      smart-money: {tag}"
            except Exception:
                pass
        lines.append(line)

    if include_news:
        news = data.get_news(symbols, limit=6)
        if news:
            lines.append("Recent market headlines:")
            for n in news:
                lines.append(f"  - {n['headline']} ({n['created_at']})")

    lines.append(f"(Data sources: {', '.join(data.sources())}. Free feeds — may lag slightly.)")
    return "\n".join(lines)


def account_and_positions_text(broker, data) -> str:
    acct = broker.get_account(data.get_price)
    lines = [
        "[YOUR PAPER ACCOUNT — simulated money]",
        f"  Equity: ${acct['equity']:,.2f}   Cash: ${acct['cash']:,.2f}   "
        f"Buying power: ${acct['buying_power']:,.2f}",
        f"  Day P/L: ${acct['day_pl']:,.2f} ({acct['day_pl_pct']:+.2f}%)",
    ]
    positions = broker.get_positions(data.get_price)
    if positions:
        lines.append("  Open positions:")
        for p in positions:
            lines.append(
                f"    {p['symbol']}: {p['qty']:g} @ ${p['avg_entry']:,.2f} "
                f"-> ${p['current_price']:,.2f}  "
                f"P/L ${p['unrealized_pl']:,.2f} ({p['unrealized_plpc']:+.2f}%)"
            )
    else:
        lines.append("  Open positions: none")
    return "\n".join(lines)
