"""Load trades and pair them into closed round-trips.

Sources: the app's own paper-trade journal (default) or an uploaded broker CSV.
Pairing is FIFO per symbol and handles both long (buy→sell) and short (sell→buy)
round-trips, plus partial fills. This is the foundation of the "shadow account"
behavior analysis (ported in spirit from Vibe-Trading's shadow account).
"""
from __future__ import annotations

import csv
import io
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from trading_llm.memory import journal


@dataclass
class RoundTrip:
    symbol: str
    side: str            # "long" or "short"
    qty: float
    entry_ts: str
    exit_ts: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    hold_days: float


def _parse_ts(ts: str) -> datetime | None:
    s = str(ts).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%Y-%m-%d", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:len(fmt) + 2].strip(), fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def from_journal() -> list[dict]:
    """Normalized fills from the local paper-trade journal."""
    out = []
    for e in journal.all_entries():
        if e.get("type") != "trade":
            continue
        if e.get("status") not in (None, "filled"):
            continue
        price, qty = e.get("price"), e.get("qty")
        if not price or not qty:
            continue
        out.append({"ts": e.get("ts", ""), "symbol": str(e.get("symbol", "")).upper(),
                    "side": str(e.get("side", "")).lower(), "qty": float(qty), "price": float(price)})
    out.sort(key=lambda t: t["ts"])
    return out


_COL = {
    "ts": ("date", "time", "datetime", "filled at", "transaction date", "trade date"),
    "symbol": ("symbol", "ticker", "instrument", "name", "stock"),
    "side": ("side", "action", "type", "buy/sell", "direction"),
    "qty": ("qty", "quantity", "shares", "size", "amount", "filled qty"),
    "price": ("price", "fill price", "avg price", "filled avg price", "execution price"),
}


def _find(headers: list[str], keys: tuple) -> str | None:
    low = {h.lower().strip(): h for h in headers}
    for k in keys:
        if k in low:
            return low[k]
    for k in keys:  # loose contains-match
        for h_low, h in low.items():
            if k in h_low:
                return h
    return None


def from_csv(text: str) -> list[dict]:
    """Best-effort parse of a broker trade export into normalized fills."""
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    cmap = {field: _find(headers, keys) for field, keys in _COL.items()}
    if not (cmap["symbol"] and cmap["side"] and cmap["price"]):
        return []
    out = []
    for row in reader:
        try:
            side_raw = str(row.get(cmap["side"], "")).lower()
            side = "buy" if side_raw.startswith(("b", "buy", "long")) else "sell"
            qty = float(str(row.get(cmap["qty"], "1") or "1").replace(",", "")) if cmap["qty"] else 1.0
            price = float(str(row.get(cmap["price"], "0")).replace("$", "").replace(",", ""))
            if price <= 0:
                continue
            out.append({"ts": str(row.get(cmap["ts"], "")) if cmap["ts"] else "",
                        "symbol": str(row.get(cmap["symbol"], "")).upper().strip(),
                        "side": side, "qty": abs(qty), "price": price})
        except Exception:
            continue
    out.sort(key=lambda t: t["ts"])
    return out


def pair_trades(fills: list[dict]) -> list[RoundTrip]:
    """FIFO-match fills into closed round-trips (long and short)."""
    # per symbol: a deque of open lots (signed qty, price, ts)
    books: dict[str, deque] = {}
    trips: list[RoundTrip] = []

    for f in fills:
        sym = f["symbol"]
        signed = f["qty"] if f["side"] == "buy" else -f["qty"]
        book = books.setdefault(sym, deque())

        # Same direction as the front lot (or empty) -> opening/adding.
        while signed != 0 and book and (book[0][0] > 0) != (signed > 0):
            lot_qty, lot_price, lot_ts = book[0]
            match = min(abs(lot_qty), abs(signed))
            entry_price, exit_price = lot_price, f["price"]
            long_side = lot_qty > 0
            pnl_per = (exit_price - entry_price) if long_side else (entry_price - exit_price)
            d0, d1 = _parse_ts(lot_ts), _parse_ts(f["ts"])
            hold = abs((d1 - d0).total_seconds()) / 86400 if d0 and d1 else 0.0
            trips.append(RoundTrip(
                symbol=sym, side="long" if long_side else "short", qty=round(match, 6),
                entry_ts=str(lot_ts), exit_ts=str(f["ts"]),
                entry_price=round(entry_price, 4), exit_price=round(exit_price, 4),
                pnl=round(pnl_per * match, 2),
                pnl_pct=round(pnl_per / entry_price * 100, 2) if entry_price else 0.0,
                hold_days=round(hold, 2)))
            # shrink lot + incoming
            new_lot = lot_qty - match if long_side else lot_qty + match
            if abs(new_lot) < 1e-9:
                book.popleft()
            else:
                book[0] = (new_lot, lot_price, lot_ts)
            signed = signed + match if signed < 0 else signed - match

        if signed != 0:  # remaining opens a new lot
            book.append((signed, f["price"], f["ts"]))

    return trips


def load_round_trips(csv_text: str | None = None) -> list[RoundTrip]:
    fills = from_csv(csv_text) if csv_text else from_journal()
    return pair_trades(fills)
