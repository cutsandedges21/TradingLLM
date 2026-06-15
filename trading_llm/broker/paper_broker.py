"""Local mock paper-trading account (no broker account needed).

Keeps cash + positions in memory/paper_account.json and simulates fills at the
current live price from the data layer. Gives you the full $100k paper experience
(buy, sell, positions, P/L) entirely on your laptop. Selling more than you hold
opens a short (profit when price falls), which keeps the simulator flexible.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date

from trading_llm.core.paths import MEMORY_DIR, load_json, save_json

ACCOUNT_PATH = MEMORY_DIR / "paper_account.json"


class PaperBroker:
    def __init__(self, starting_cash: float = 100000.0):
        self.starting_cash = float(starting_cash)
        self._state = self._load()

    # ---------- persistence ----------
    def _fresh(self) -> dict:
        return {
            "cash": self.starting_cash,
            "starting_cash": self.starting_cash,
            "positions": {},   # symbol -> {qty, avg_entry}
            "orders": [],
            "day": {"date": "", "equity": self.starting_cash},
        }

    def _load(self) -> dict:
        data = load_json(ACCOUNT_PATH, None)
        if not isinstance(data, dict) or "cash" not in data:
            data = self._fresh()
            save_json(ACCOUNT_PATH, data)
            return data
        for k, v in self._fresh().items():
            data.setdefault(k, v)
        return data

    def _save(self) -> None:
        save_json(ACCOUNT_PATH, self._state)

    def reset(self, cash: float | None = None) -> None:
        self.starting_cash = float(cash) if cash is not None else self.starting_cash
        self._state = self._fresh()
        self._save()

    # ---------- reads ----------
    def get_positions(self, price_fn) -> list[dict]:
        out = []
        for sym, pos in self._state["positions"].items():
            q = pos["qty"]
            avg = pos["avg_entry"]
            price = price_fn(sym) or avg
            mv = q * price
            cost = q * avg
            pl = mv - cost  # works for shorts: q<0 -> profit when price falls
            plpc = (pl / abs(cost) * 100) if cost else 0.0
            out.append({
                "symbol": sym,
                "qty": round(q, 6),
                "side": "short" if q < 0 else "long",
                "avg_entry": round(avg, 2),
                "current_price": round(price, 2),
                "market_value": round(mv, 2),
                "unrealized_pl": round(pl, 2),
                "unrealized_plpc": round(plpc, 2),
            })
        return out

    def _equity(self, price_fn) -> float:
        held = sum(p["market_value"] for p in self.get_positions(price_fn))
        return self._state["cash"] + held

    def get_account(self, price_fn) -> dict:
        equity = self._equity(price_fn)
        today = date.today().isoformat()
        day = self._state.get("day", {})
        if day.get("date") != today:
            day = {"date": today, "equity": equity}
            self._state["day"] = day
            self._save()
        base = day["equity"] or equity
        return {
            "equity": round(equity, 2),
            "cash": round(self._state["cash"], 2),
            "buying_power": round(self._state["cash"], 2),  # no margin in mock
            "portfolio_value": round(equity, 2),
            "day_pl": round(equity - base, 2),
            "day_pl_pct": round((equity / base - 1) * 100, 2) if base else 0.0,
            "currency": "USD",
            "status": "MOCK",
        }

    # ---------- orders ----------
    def place_order(self, symbol: str, side: str, qty: float | None = None,
                    notional: float | None = None, price_fn=None,
                    order_type: str = "market", limit_price: float | None = None,
                    slippage_bps: float = 0.0, fee_bps: float = 0.0) -> dict:
        """Simulate a fill. Optional realism: market orders slip against you by
        ``slippage_bps`` and a ``fee_bps`` commission is charged on notional."""
        side = str(side).lower()
        price = price_fn(symbol) if price_fn else None
        if not price:
            return {"error": f"No live price for {symbol}; can't simulate a fill right now."}

        if order_type == "limit" and limit_price:
            lp = float(limit_price)
            if side == "buy" and price > lp:
                return {"error": f"Limit buy ${lp:g} isn't marketable (price ${price:.2f}). "
                                 f"Mock broker is fill-or-cancel — try a market order or higher limit."}
            if side == "sell" and price < lp:
                return {"error": f"Limit sell ${lp:g} isn't marketable (price ${price:.2f})."}
            fill = lp  # limit orders fill at the limit, no slippage
        else:
            slip = float(slippage_bps) / 10000.0  # market orders slip against you
            fill = float(price) * (1 + slip) if side == "buy" else float(price) * (1 - slip)

        if qty is None and notional:
            qty = float(notional) / fill
        if not qty or qty <= 0:
            return {"error": "Invalid quantity."}
        qty = float(qty)
        fee = abs(qty * fill) * float(fee_bps) / 10000.0
        positions = self._state["positions"]
        delta = qty if side == "buy" else -qty  # signed change (+long / -short)

        pos = positions.get(symbol)
        old = pos["qty"] if pos else 0.0
        old_avg = pos["avg_entry"] if pos else 0.0
        new = old + delta

        # Buying needs cash (no margin). Selling/shorting receives cash. Fee always costs cash.
        if side == "buy" and qty * fill + fee > self._state["cash"] + 1e-6:
            return {"error": f"Insufficient cash: need ${qty * fill + fee:,.2f}, "
                             f"have ${self._state['cash']:,.2f}."}

        self._state["cash"] -= delta * fill + fee

        if abs(new) < 1e-9:
            positions.pop(symbol, None)  # fully closed
        else:
            if old == 0 or (old > 0) == (delta > 0):
                # opening, or adding in the same direction -> weighted average entry
                avg = (abs(old) * old_avg + abs(delta) * fill) / (abs(old) + abs(delta))
            elif abs(delta) <= abs(old):
                # reducing the existing position -> entry unchanged
                avg = old_avg
            else:
                # flipped through zero (long <-> short) -> new entry at fill
                avg = fill
            positions[symbol] = {"qty": new, "avg_entry": avg}

        order = {
            "id": uuid.uuid4().hex,
            "symbol": symbol,
            "side": side,
            "qty": round(qty, 6),
            "status": "filled",
            "filled_avg_price": round(fill, 2),
            "fee": round(fee, 2),
            "slippage_bps": float(slippage_bps),
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._state["orders"].append(order)
        self._save()
        return order
