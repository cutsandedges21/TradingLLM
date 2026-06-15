"""Congressional trading disclosures — the *degradable* smart-money source.

There is no official, free, no-key API for congressional STOCK Act disclosures.
Community datasets (house/senate-stock-watcher) come and go and are often gated.
So this module ships a **correct, fixture-tested parser** plus a **configurable**
fetcher: the endpoints live in settings, and any failure degrades cleanly to
"unavailable" (never an exception, never fabricated data). When the user points
``signals.congress_sources`` at a working/keyed JSON source, it lights up with no
code change.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta

from trading_llm.signals.models import Signal, CONGRESS

CONGRESS_LAG = "varies (often weeks)"

# Default public endpoints (may be gated/unavailable — handled gracefully).
DEFAULT_SOURCES = [
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json",
]

_BUY = {"purchase", "buy", "p", "exchange"}
_SELL = {"sale", "sale_full", "sale_partial", "sell", "s"}


def _midpoint_amount(amount) -> float:
    """'$1,001 - $15,000' -> 8000.5; single numbers pass through; junk -> 0.0."""
    if amount is None:
        return 0.0
    if isinstance(amount, (int, float)):
        return float(amount)
    s = str(amount).replace("$", "").replace(",", "").strip()
    if "-" in s:
        parts = [p.strip() for p in s.split("-") if p.strip()]
        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except Exception:
                pass
        if nums:
            return sum(nums) / len(nums)
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def _row_get(row: dict, *keys: str) -> str:
    for k in keys:
        if k in row and row[k]:
            return str(row[k])
    return ""


def parse_congress(json_text: str, *, as_of: str = "", now: datetime | None = None,
                   lookback_days: int = 365) -> list[Signal]:
    """Parse a house/senate-stock-watcher-style JSON array into Signals. Fail-soft → []."""
    now = now or datetime.now()
    cutoff = (now - timedelta(days=lookback_days)).date()
    try:
        rows = json.loads(json_text)
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    out: list[Signal] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = _row_get(row, "ticker", "symbol").upper()
        if not ticker or ticker in ("--", "N/A", "NONE"):
            continue
        ttype = _row_get(row, "type", "transaction_type").lower()
        direction = 1 if any(b in ttype for b in _BUY) else (-1 if any(s in ttype for s in _SELL) else 0)
        if direction == 0:
            continue
        date = _row_get(row, "transaction_date", "transactionDate", "date")[:10]
        try:
            if date and datetime.strptime(date, "%Y-%m-%d").date() < cutoff:
                continue
        except Exception:
            pass
        who = _row_get(row, "representative", "senator", "name", "member") or "Member of Congress"
        amt = _midpoint_amount(row.get("amount") or row.get("amount_range"))
        out.append(Signal(
            kind=CONGRESS, symbol=ticker, date=date, actor=who, direction=direction,
            size_usd=amt, as_of=as_of, lag_note=CONGRESS_LAG,
            detail=f"{who} {'bought' if direction > 0 else 'sold'} {ticker}"
                   + (f" ({row.get('amount')})" if row.get("amount") else ""),
            source_url=_row_get(row, "ptr_link", "link", "source_url"),
        ))
    return out


def fetch_congress_index(ua: str, sources: list[str] | None = None, *,
                         lookback_days: int = 365, timeout: int = 25) -> dict:
    """Fetch + index congressional trades as {TICKER: [Signal]}. Fail-soft.

    Returns {'index': {...}, 'available': bool}. ``available`` is False when no
    source could be fetched, so callers can show 'congress: unavailable'.
    """
    as_of = datetime.now().strftime("%Y-%m-%d")
    sources = sources if sources is not None else DEFAULT_SOURCES
    index: dict[str, list[Signal]] = {}
    available = False
    for url in sources:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
        except Exception:
            continue
        sigs = parse_congress(body, as_of=as_of, lookback_days=lookback_days)
        if sigs:
            available = True
        for s in sigs:
            index.setdefault(s.symbol, []).append(s)
    return {"index": index, "available": available}
