"""Persistent trade & observation journal — the long-term market memory.

Stored as memory/journal.json (a growing list). Every paper trade, every notable
observation, and a rolling record of chats are appended here and fed back into
the model, so it 'learns' your history over time without any training.
"""
from __future__ import annotations

from datetime import datetime, date
from threading import Lock

from trading_llm.core.paths import MEMORY_DIR, load_json, save_json

JOURNAL_PATH = MEMORY_DIR / "journal.json"
_lock = Lock()


def _load() -> list:
    data = load_json(JOURNAL_PATH, [])
    return data if isinstance(data, list) else []


def add_entry(entry_type: str, **fields) -> dict:
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), "type": entry_type}
    entry.update({k: v for k, v in fields.items() if v is not None})
    with _lock:
        data = _load()
        data.append(entry)
        save_json(JOURNAL_PATH, data)
    return entry


def all_entries() -> list:
    return _load()


def recent(n: int = 20, entry_type: str | None = None, symbol: str | None = None) -> list:
    data = _load()
    if entry_type:
        data = [e for e in data if e.get("type") == entry_type]
    if symbol:
        data = [e for e in data if str(e.get("symbol", "")).upper() == symbol.upper()]
    return data[-n:]


def trades_today() -> int:
    today = date.today().isoformat()
    return sum(
        1 for e in _load()
        if e.get("type") == "trade" and str(e.get("ts", "")).startswith(today)
    )


def delete_trade(ts: str, symbol: str | None = None) -> bool:
    """Remove the first matching trade entry (used by the Trade page ✕ button)."""
    with _lock:
        data = _load()
        for i, e in enumerate(data):
            if (e.get("type") == "trade" and e.get("ts") == ts
                    and (symbol is None or e.get("symbol") == symbol)):
                del data[i]
                save_json(JOURNAL_PATH, data)
                return True
    return False


def format_for_prompt(n: int = 12) -> str:
    data = _load()
    if not data:
        return ""
    lines = []
    for e in data[-n:]:
        ts = str(e.get("ts", ""))[:16].replace("T", " ")
        t = e.get("type", "note")
        if t == "trade":
            lines.append(
                f"  [{ts}] TRADE {str(e.get('side', '')).upper()} {e.get('qty')} "
                f"{e.get('symbol')} @ {e.get('price', '?')} ({e.get('status', '')}) "
                f"— {str(e.get('rationale', ''))[:120]}"
            )
        elif t == "observation":
            lines.append(f"  [{ts}] NOTE {e.get('symbol', '')}: {str(e.get('content', ''))[:150]}")
        else:
            lines.append(f"  [{ts}] {t}: {str(e.get('content', ''))[:150]}")
    return "[RECENT JOURNAL — your past notes, advice, and paper trades]\n" + "\n".join(lines)
