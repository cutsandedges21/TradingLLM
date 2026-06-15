"""Build an aligned OHLCV panel for a universe of symbols.

A "panel" is a dict of **wide** DataFrames (index = date, columns = symbol) for
each field — open/high/low/close/volume — plus a precomputed ``returns`` frame.
Factors and the IC bench operate cross-sectionally across the columns, so a
universe needs enough symbols (>= ~5) that share a common trading calendar. Built
from the free backtest data loader; crypto is excluded (different calendar).
"""
from __future__ import annotations

import pandas as pd

from trading_llm.backtest.data import load_ohlc
from trading_llm.market.data import is_crypto

FIELDS = ("open", "high", "low", "close", "volume")


def build_panel(symbols: list[str], period: str = "2y",
                interval: str = "1d", min_symbols: int = 5) -> dict[str, pd.DataFrame] | None:
    """Load each symbol and assemble aligned wide frames. None if too few load."""
    equities = [s for s in symbols if not is_crypto(s)]
    cols: dict[str, dict[str, pd.Series]] = {f: {} for f in FIELDS}
    loaded: list[str] = []

    for sym in equities:
        df = load_ohlc(sym, period, interval)
        if df is None or "close" not in df:
            continue
        loaded.append(sym)
        for f in FIELDS:
            if f in df.columns:
                cols[f][sym] = df[f]

    if len(loaded) < min_symbols:
        return None

    panel: dict[str, pd.DataFrame] = {}
    for f in FIELDS:
        if cols[f]:
            wide = pd.DataFrame(cols[f]).sort_index()
            # tz-naive index so symbols from the same calendar align exactly
            try:
                wide.index = wide.index.tz_localize(None)
            except (TypeError, AttributeError):
                pass
            panel[f] = wide

    if "close" not in panel:
        return None
    panel["returns"] = panel["close"].pct_change()
    panel["_symbols"] = loaded  # type: ignore  (metadata, ignored by operators)
    return panel
