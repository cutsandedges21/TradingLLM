"""Thin, defensive wrapper around alpaca-py (data + paper trading).

Design goals:
- Never crash the app: every network call is guarded; failures return None/[]/error dict.
- Crypto data works with no keys; stocks + trading need your Alpaca paper keys.
- All trading goes through a paper account (paper=True) unless you flip it off.

``alpaca-py`` is an OPTIONAL dependency. This module is only imported lazily by
``AlpacaProvider`` (when "alpaca" is in the data-source order), and that import
is wrapped in try/except by the caller, so a missing lib degrades gracefully.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# --- alpaca-py imports (verified against 0.43.4) ---
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest, StockLatestTradeRequest,
    CryptoBarsRequest, CryptoLatestQuoteRequest,
)
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

try:  # news endpoint location can vary; treat as optional
    from alpaca.data.historical.news import NewsClient
    from alpaca.data.requests import NewsRequest
    _NEWS_OK = True
except Exception:  # pragma: no cover
    _NEWS_OK = False


def is_crypto(symbol: str) -> bool:
    return "/" in symbol


_TF = {
    "1Min": TimeFrame.Minute,
    "1Hour": TimeFrame.Hour,
    "1Day": TimeFrame.Day,
    "1Week": TimeFrame.Week,
}


class AlpacaClient:
    def __init__(self, api_key: str = "", secret_key: str = "", paper: bool = True):
        self.api_key = (api_key or "").strip()
        self.secret_key = (secret_key or "").strip()
        self.paper = paper
        self.has_keys = bool(self.api_key and self.secret_key)
        self.last_error: str | None = None

        # Crypto data needs no keys at all.
        self.crypto_data = CryptoHistoricalDataClient()

        if self.has_keys:
            try:
                self.trading = TradingClient(self.api_key, self.secret_key, paper=paper)
                self.stock_data = StockHistoricalDataClient(self.api_key, self.secret_key)
                self.news = NewsClient(self.api_key, self.secret_key) if _NEWS_OK else None
            except Exception as exc:
                self.last_error = f"Alpaca init failed: {exc}"
                self.trading = None
                self.stock_data = None
                self.news = None
        else:
            self.trading = None
            self.stock_data = None
            self.news = None

    # ---------- prices & bars ----------
    def get_bars(self, symbol: str, timeframe: str = "1Day", lookback: int = 120) -> list[float]:
        """Return a list of closing prices (oldest -> newest)."""
        tf = _TF.get(timeframe, TimeFrame.Day)
        start = datetime.now(timezone.utc) - timedelta(days=max(lookback * 2, 40))
        try:
            if is_crypto(symbol):
                req = CryptoBarsRequest(symbol_or_symbols=[symbol], timeframe=tf, start=start)
                barset = self.crypto_data.get_crypto_bars(req)
            else:
                if not self.stock_data:
                    return []
                req = StockBarsRequest(symbol_or_symbols=[symbol], timeframe=tf,
                                       start=start, feed=DataFeed.IEX)
                barset = self.stock_data.get_stock_bars(req)
            df = barset.df
            if df is None or df.empty:
                return []
            if df.index.nlevels > 1:  # (symbol, timestamp) MultiIndex
                try:
                    df = df.xs(symbol, level=0)
                except Exception:
                    df = df.droplevel(0)
            return [float(x) for x in df["close"].tolist()][-lookback:]
        except Exception as exc:
            self.last_error = f"get_bars({symbol}): {exc}"
            return []

    def get_price(self, symbol: str) -> float | None:
        try:
            if is_crypto(symbol):
                req = CryptoLatestQuoteRequest(symbol_or_symbols=[symbol])
                q = self.crypto_data.get_crypto_latest_quote(req)[symbol]
                mid = (float(q.ask_price) + float(q.bid_price)) / 2
                return mid if mid > 0 else float(q.ask_price) or float(q.bid_price)
            if not self.stock_data:
                return None
            req = StockLatestTradeRequest(symbol_or_symbols=[symbol], feed=DataFeed.IEX)
            trade = self.stock_data.get_stock_latest_trade(req)[symbol]
            return float(trade.price)
        except Exception as exc:
            self.last_error = f"get_price({symbol}): {exc}"
            return None

    # ---------- account & positions ----------
    def get_account(self) -> dict | None:
        if not self.trading:
            return None
        try:
            a = self.trading.get_account()
            equity = float(a.equity)
            last_equity = float(a.last_equity)
            return {
                "equity": equity,
                "cash": float(a.cash),
                "buying_power": float(a.buying_power),
                "portfolio_value": float(a.portfolio_value),
                "day_pl": round(equity - last_equity, 2),
                "day_pl_pct": round((equity / last_equity - 1) * 100, 2) if last_equity else 0.0,
                "currency": a.currency,
                "status": str(a.status),
            }
        except Exception as exc:
            self.last_error = f"get_account: {exc}"
            return None

    def get_positions(self) -> list[dict]:
        if not self.trading:
            return []
        try:
            out = []
            for p in self.trading.get_all_positions():
                out.append({
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "side": str(getattr(p, "side", "long")),
                    "avg_entry": float(p.avg_entry_price),
                    "current_price": float(p.current_price) if p.current_price else None,
                    "market_value": float(p.market_value) if p.market_value else None,
                    "unrealized_pl": float(p.unrealized_pl) if p.unrealized_pl else 0.0,
                    "unrealized_plpc": round(float(p.unrealized_plpc) * 100, 2) if p.unrealized_plpc else 0.0,
                })
            return out
        except Exception as exc:
            self.last_error = f"get_positions: {exc}"
            return []

    # ---------- news (optional) ----------
    def get_news(self, symbols: list[str], limit: int = 8) -> list[dict]:
        if not self.news or not symbols:
            return []
        stock_syms = [s for s in symbols if not is_crypto(s)]
        if not stock_syms:
            return []
        try:
            resp = self.news.get_news(NewsRequest(symbols=",".join(stock_syms), limit=limit))
            raw = getattr(resp, "data", None)
            items = raw.get("news") if isinstance(raw, dict) else getattr(resp, "news", [])
            out = []
            for n in (items or [])[:limit]:
                out.append({
                    "headline": getattr(n, "headline", ""),
                    "created_at": str(getattr(n, "created_at", ""))[:16],
                    "symbols": getattr(n, "symbols", []),
                })
            return out
        except Exception as exc:
            self.last_error = f"get_news: {exc}"
            return []

    # ---------- market clock ----------
    def market_open(self) -> bool | None:
        if not self.trading:
            return None
        try:
            return bool(self.trading.get_clock().is_open)
        except Exception:
            return None

    # ---------- paper trading ----------
    def place_order(self, symbol: str, side: str, qty: float | None = None,
                    notional: float | None = None, order_type: str = "market",
                    limit_price: float | None = None) -> dict:
        """Submit a paper order. Returns a dict with status or an 'error' key."""
        if not self.trading:
            return {"error": "No Alpaca keys configured — add them in config/api_keys.json."}
        try:
            side_enum = OrderSide.BUY if str(side).lower() == "buy" else OrderSide.SELL
            tif = TimeInForce.GTC if is_crypto(symbol) else TimeInForce.DAY
            common = {"symbol": symbol, "side": side_enum, "time_in_force": tif}
            if qty is not None:
                common["qty"] = float(qty)
            elif notional is not None:
                common["notional"] = float(notional)
            else:
                return {"error": "Specify either qty or notional."}

            if order_type == "limit" and limit_price:
                req = LimitOrderRequest(limit_price=float(limit_price), **common)
            else:
                req = MarketOrderRequest(**common)

            o = self.trading.submit_order(req)
            return {
                "id": str(o.id),
                "symbol": o.symbol,
                "side": str(o.side).split(".")[-1].lower(),
                "qty": float(o.qty) if o.qty else qty,
                "status": str(o.status).split(".")[-1].lower(),
                "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
                "submitted_at": str(o.submitted_at)[:19],
            }
        except Exception as exc:
            return {"error": str(exc)}

    def recent_orders(self, limit: int = 10) -> list[dict]:
        if not self.trading:
            return []
        try:
            req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit)
            out = []
            for o in self.trading.get_orders(req):
                out.append({
                    "symbol": o.symbol,
                    "side": str(o.side).split(".")[-1].lower(),
                    "qty": float(o.qty) if o.qty else None,
                    "status": str(o.status).split(".")[-1].lower(),
                    "submitted_at": str(o.submitted_at)[:19],
                })
            return out
        except Exception as exc:
            self.last_error = f"recent_orders: {exc}"
            return []
