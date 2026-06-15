"""Decision log — records each analysis decision so outcomes can be reflected on.

Phase 0 ships a small, functional JSON log; Phase 1's reflection loop (ported from
TradingAgents) fills in realized returns + a one-paragraph lesson and re-injects
recent same-ticker decisions and cross-ticker lessons into future prompts.

Schema (memory/decision_log.json is a list of):
    {
      "ticker": "NVDA", "date": "2026-06-11", "decision": "...full text...",
      "created": "2026-06-11T13:24:00",
      "raw_return": null, "alpha_return": null, "holding_days": null,
      "reflection": null   # filled once the outcome is known
    }
An entry is "pending" while ``reflection`` is null.
"""
from __future__ import annotations

from datetime import datetime
from threading import Lock

from trading_llm.core.paths import MEMORY_DIR, load_json, save_json

LOG_PATH = MEMORY_DIR / "decision_log.json"
_lock = Lock()


def _load() -> list:
    data = load_json(LOG_PATH, [])
    return data if isinstance(data, list) else []


def _save(data: list) -> None:
    save_json(LOG_PATH, data)


def store_decision(ticker: str, trade_date, decision: str) -> dict:
    """Append a new (pending) decision entry."""
    entry = {
        "ticker": str(ticker).upper(),
        "date": str(trade_date),
        "decision": str(decision),
        "created": datetime.now().isoformat(timespec="seconds"),
        "raw_return": None,
        "alpha_return": None,
        "holding_days": None,
        "reflection": None,
    }
    with _lock:
        data = _load()
        data.append(entry)
        _save(data)
    return entry


def get_pending_entries(ticker: str | None = None) -> list:
    """Entries whose outcome has not been reflected on yet."""
    out = []
    for e in _load():
        if e.get("reflection"):
            continue
        if ticker and e.get("ticker", "").upper() != ticker.upper():
            continue
        out.append(e)
    return out


def batch_update_with_outcomes(updates: list[dict]) -> int:
    """Attach realized returns + reflection to matching (ticker, date) entries.

    Each update: {ticker, trade_date, raw_return, alpha_return, holding_days, reflection}.
    Returns the number of entries updated.
    """
    if not updates:
        return 0
    index = {(u["ticker"].upper(), str(u["trade_date"])): u for u in updates}
    changed = 0
    with _lock:
        data = _load()
        for e in data:
            key = (e.get("ticker", "").upper(), str(e.get("date")))
            u = index.get(key)
            if u and not e.get("reflection"):
                e["raw_return"] = u.get("raw_return")
                e["alpha_return"] = u.get("alpha_return")
                e["holding_days"] = u.get("holding_days")
                e["reflection"] = u.get("reflection")
                changed += 1
        if changed:
            _save(data)
    return changed


def recent_lessons(n: int = 5) -> list[str]:
    """Most recent reflections across all tickers (cross-ticker lessons)."""
    reflected = [e for e in _load() if e.get("reflection")]
    return [e["reflection"] for e in reflected[-n:]]


def get_past_context(ticker: str, n_ticker: int = 3, n_lessons: int = 3) -> str:
    """Format recent same-ticker decisions + cross-ticker lessons for prompt injection."""
    data = _load()
    same = [e for e in data if e.get("ticker", "").upper() == ticker.upper()][-n_ticker:]
    lessons = recent_lessons(n_lessons)
    if not same and not lessons:
        return ""
    lines: list[str] = []
    if same:
        lines.append(f"[PAST DECISIONS ON {ticker.upper()}]")
        for e in same:
            outcome = ""
            if e.get("alpha_return") is not None:
                outcome = f" (alpha {e['alpha_return']:+.1%})"
            refl = e.get("reflection") or "outcome pending"
            lines.append(f"  - {e.get('date')}{outcome}: {refl}")
    if lessons:
        lines.append("[RECENT LESSONS ACROSS TICKERS]")
        for l in lessons:
            lines.append(f"  - {l}")
    return "\n".join(lines)
