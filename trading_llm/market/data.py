"""Multi-source market data with automatic fallback + caching.

Price (per source capability):
  - Finnhub  -> real-time US stock quotes (free tier), needs a free API key
  - yfinance -> stocks + crypto bars and prices (no key, Yahoo Finance)
  - Alpaca   -> crypto (keyless) and stocks (only if you add keys)

Bars (for indicators) come from yfinance (Finnhub candles are premium-only).
Order is configurable via settings 'data_source_order'. Everything is cached
briefly so the watchlist, positions, and the LLM snapshot share one fetch.

Third-party libs are imported defensively so importing this module never fails
when an optional lib is absent; live methods simply degrade to no data.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore
try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None  # type: ignore
try:
    import finnhub
except Exception:  # pragma: no cover
    finnhub = None  # type: ignore

from trading_llm.core.config import finnhub_key

try:
    from zoneinfo import ZoneInfo
    _NY = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _NY = None


def is_crypto(symbol: str) -> bool:
    return "/" in symbol or symbol.upper().endswith("-USD")


def to_yf(symbol: str) -> str:
    # "BTC/USD" -> "BTC-USD"; stocks unchanged.
    return symbol.replace("/", "-")


# yfinance period/interval for each timeframe
_YF_TF = {
    "1Min": ("5d", "1m"),
    "1Hour": ("1mo", "1h"),
    "1Day": ("1y", "1d"),
    "1Week": ("5y", "1wk"),
}

# Binance public klines (crypto) — the only free source with sub-minute (1s) bars.
# Note: api.binance.com is geo-blocked in some regions (e.g. the US -> HTTP 451);
# callers fall back gracefully when it returns nothing.
_BINANCE_URL = "https://api.binance.com/api/v3/klines"
_BIN_INTERVAL = {
    "1S": "1s", "5S": "1s", "30S": "1s",
    "1M": "1m", "5M": "5m", "15M": "15m", "30M": "30m",
    "1H": "1h", "1D": "1d", "1W": "1w",
}
_BIN_AGG = {"5S": 5, "30S": 30}  # build these from 1s bars


def to_binance_pair(symbol: str) -> str:
    base = (symbol.upper().replace("/USD", "").replace("-USD", "")
            .replace("USDT", "").replace("USD", "").strip())
    return base + "USDT" if base else ""


class YFinanceProvider:
    name = "yfinance"

    def get_bars(self, symbol: str, timeframe: str = "1Day", lookback: int = 120) -> list[float]:
        if yf is None:
            return []
        period, interval = _YF_TF.get(timeframe, ("1y", "1d"))
        try:
            df = yf.Ticker(to_yf(symbol)).history(period=period, interval=interval, auto_adjust=True)
            if df is None or df.empty or "Close" not in df:
                return []
            return [float(x) for x in df["Close"].dropna().tolist()][-lookback:]
        except Exception:
            return []

    def get_price(self, symbol: str) -> float | None:
        if yf is None:
            return None
        try:
            fi = yf.Ticker(to_yf(symbol)).fast_info
            for key in ("last_price", "lastPrice", "last_close", "previous_close"):
                try:
                    val = fi[key] if hasattr(fi, "__getitem__") else getattr(fi, key, None)
                except Exception:
                    val = getattr(fi, key, None)
                if val:
                    return float(val)
        except Exception:
            pass
        bars = self.get_bars(symbol, "1Day", 3)
        return bars[-1] if bars else None


class FinnhubProvider:
    name = "finnhub"

    def __init__(self, api_key: str):
        self.client = finnhub.Client(api_key=api_key)

    def get_price(self, symbol: str) -> float | None:
        if is_crypto(symbol):
            return None  # free tier crypto is awkward; let yfinance handle it
        try:
            q = self.client.quote(symbol)
            c = q.get("c")
            return float(c) if c else None
        except Exception:
            return None

    def get_bars(self, symbol: str, timeframe: str = "1Day", lookback: int = 120) -> list[float]:
        return []  # Finnhub candles are premium-only; yfinance covers bars

    def news(self, limit: int = 6) -> list[dict]:
        try:
            items = self.client.general_news("general") or []
            out = []
            for n in items[:limit]:
                ts = n.get("datetime")
                when = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
                out.append({"headline": n.get("headline", ""), "created_at": when, "symbols": []})
            return out
        except Exception:
            return []


class AlpacaProvider:
    name = "alpaca"

    def __init__(self, keys: dict):
        from trading_llm.market.alpaca_client import AlpacaClient
        self.client = AlpacaClient(keys.get("alpaca_paper_key", ""),
                                   keys.get("alpaca_paper_secret", ""),
                                   paper=keys.get("alpaca_paper", True))

    def get_price(self, symbol: str) -> float | None:
        if not is_crypto(symbol) and not self.client.has_keys:
            return None
        return self.client.get_price(symbol)

    def get_bars(self, symbol: str, timeframe: str = "1Day", lookback: int = 120) -> list[float]:
        if not is_crypto(symbol) and not self.client.has_keys:
            return []
        return self.client.get_bars(symbol, timeframe, lookback)


class MarketData:
    """Aggregates providers with fallback + light TTL caching."""

    def __init__(self, settings: dict, keys: dict):
        order = settings.get("data_source_order", ["finnhub", "yfinance", "alpaca"])
        self.providers = []
        self._finnhub: FinnhubProvider | None = None
        for name in order:
            if name == "finnhub" and finnhub_key(keys) and finnhub is not None:
                self._finnhub = FinnhubProvider(finnhub_key(keys))
                self.providers.append(self._finnhub)
            elif name == "yfinance":
                self.providers.append(YFinanceProvider())
            elif name == "alpaca":
                try:
                    self.providers.append(AlpacaProvider(keys))
                except Exception:
                    pass
        self._price_cache: dict[str, tuple[float, float | None]] = {}
        self._last_good: dict[str, float] = {}   # never lose a real price
        self._bars_cache: dict[tuple, tuple[float, list[float]]] = {}
        self._ohlc_cache: dict[tuple, tuple[float, list[dict]]] = {}
        self._price_ttl = 8    # shared cache throttles provider hits under polling
        self._bars_ttl = 60
        self._ohlc_ttl = 20

    def sources(self) -> list[str]:
        return [p.name for p in self.providers]

    def _binance_price(self, symbol: str) -> float | None:
        if requests is None:
            return None
        pair = to_binance_pair(symbol)
        if not pair:
            return None
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price",
                             params={"symbol": pair}, timeout=6)
            if r.status_code == 200:
                return float(r.json()["price"])
        except Exception:
            pass
        return None

    def _fetch_price(self, symbol: str) -> float | None:
        # crypto: Binance first (reliable, no rate limit), then the provider chain
        if is_crypto(symbol):
            p = self._binance_price(symbol)
            if p:
                return p
        for prov in self.providers:
            try:
                price = prov.get_price(symbol)
            except Exception:
                price = None
            if price:
                return price
        return None

    def get_price(self, symbol: str) -> float | None:
        now = time.time()
        hit = self._price_cache.get(symbol)
        if hit and hit[1] is not None and now - hit[0] < self._price_ttl:
            return hit[1]
        price = self._fetch_price(symbol)
        if price is not None:
            self._price_cache[symbol] = (now, price)
            self._last_good[symbol] = price
            return price
        # everything failed -> last known real price, so positions still mark to market
        return self._last_good.get(symbol)

    def get_price_fresh(self, symbol: str) -> float | None:
        """Bypass the cache — used by the live tick chart for real-time bars."""
        price = self._fetch_price(symbol)
        if price is not None:
            self._price_cache[symbol] = (time.time(), price)
            self._last_good[symbol] = price
            return price
        return self._last_good.get(symbol)

    def get_bars(self, symbol: str, timeframe: str = "1Day", lookback: int = 120) -> list[float]:
        key = (symbol, timeframe, lookback)
        hit = self._bars_cache.get(key)
        now = time.time()
        if hit and now - hit[0] < self._bars_ttl:
            return hit[1]
        bars: list[float] = []
        for p in self.providers:
            try:
                bars = p.get_bars(symbol, timeframe, lookback)
            except Exception:
                bars = []
            if bars:
                break
        self._bars_cache[key] = (now, bars)
        return bars

    def get_news(self, symbols: list[str], limit: int = 6) -> list[dict]:
        return self._finnhub.news(limit) if self._finnhub else []

    def market_open(self) -> bool | None:
        if _NY is None:
            return None
        now = datetime.now(_NY)
        if now.weekday() >= 5:
            return False
        minutes = now.hour * 60 + now.minute
        return 9 * 60 + 30 <= minutes < 16 * 60

    def next_market_open(self) -> datetime | None:
        if _NY is None:
            return None
        now = datetime.now(_NY)
        cand = now.replace(hour=9, minute=30, second=0, microsecond=0)
        if cand <= now:
            cand += timedelta(days=1)
        while cand.weekday() >= 5:  # skip Sat/Sun
            cand += timedelta(days=1)
        return cand

    def next_open_label(self) -> str | None:
        nxt = self.next_market_open()
        if nxt is None:
            return None
        days = (nxt.date() - datetime.now(_NY).date()).days
        day = "today" if days == 0 else "tomorrow" if days == 1 else nxt.strftime("%a")
        return f"opens {day} 9:30 AM ET"

    def get_ohlc(self, symbol: str, period: str = "1y",
                 interval: str = "1d", limit: int = 400) -> list[dict]:
        """OHLC candles via yfinance (the only free source with full bars)."""
        if yf is None:
            return []
        key = (symbol, period, interval, limit)
        hit = self._ohlc_cache.get(key)
        now = time.time()
        if hit and now - hit[0] < self._ohlc_ttl:
            return hit[1]

        candles: list[dict] = []
        try:
            df = yf.Ticker(to_yf(symbol)).history(period=period, interval=interval, auto_adjust=True)
            if df is not None and not df.empty:
                daily = interval.endswith(("d", "wk", "mo"))
                for idx, row in df.tail(limit).iterrows():
                    o, h, l, c = row.get("Open"), row.get("High"), row.get("Low"), row.get("Close")
                    if any(v is None or v != v for v in (o, h, l, c)):  # skip NaN rows
                        continue
                    t = idx.strftime("%Y-%m-%d") if daily else int(idx.timestamp())
                    candles.append({
                        "time": t,
                        "open": round(float(o), 2),
                        "high": round(float(h), 2),
                        "low": round(float(l), 2),
                        "close": round(float(c), 2),
                        "volume": int(row.get("Volume") or 0),
                    })
        except Exception:
            candles = []

        self._ohlc_cache[key] = (now, candles)
        return candles

    def get_crypto_ohlc(self, symbol: str, tf: str, limit: int = 500) -> list[dict]:
        """OHLC candles for crypto from Binance — includes real sub-minute history
        (1s bars, aggregated into 5s/30s). Returns [] if Binance is unreachable."""
        if requests is None:
            return []
        tfu = tf.upper()
        interval = _BIN_INTERVAL.get(tfu)
        pair = to_binance_pair(symbol)
        if not interval or not pair:
            return []
        agg = _BIN_AGG.get(tfu)
        count = 1000 if agg else min(limit, 1000)
        key = ("BIN", pair, tfu)
        hit = self._ohlc_cache.get(key)
        now = time.time()
        ttl = 4 if agg else self._ohlc_ttl
        if hit and now - hit[0] < ttl:
            return hit[1]
        try:
            r = requests.get(_BINANCE_URL,
                             params={"symbol": pair, "interval": interval, "limit": count}, timeout=12)
            if r.status_code != 200:
                return []
            rows = r.json()
            candles = [{
                "time": int(k[0] // 1000),
                "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
                "close": float(k[4]), "volume": round(float(k[5]), 2),
            } for k in rows]
            if agg:
                candles = self._aggregate(candles, agg)
        except Exception:
            return []
        self._ohlc_cache[key] = (now, candles)
        return candles

    @staticmethod
    def _aggregate(candles: list[dict], seconds: int) -> list[dict]:
        out: list[dict] = []
        for c in candles:
            bucket = (c["time"] // seconds) * seconds
            if not out or out[-1]["time"] != bucket:
                out.append({"time": bucket, "open": c["open"], "high": c["high"],
                            "low": c["low"], "close": c["close"], "volume": c["volume"]})
            else:
                last = out[-1]
                last["high"] = max(last["high"], c["high"])
                last["low"] = min(last["low"], c["low"])
                last["close"] = c["close"]
                last["volume"] = round(last["volume"] + c["volume"], 2)
        return out
