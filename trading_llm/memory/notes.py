"""Persistent free-form notes — cross-session memory the user/agent can save & recall.

Complements the structured trader profile: this is for arbitrary facts ("I prefer
swing trades", "watching the Fed meeting on the 18th"). Stored as memory/notes.json;
recalled by lightweight keyword search and injected into chat context.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from threading import Lock

from trading_llm.core.paths import MEMORY_DIR, load_json, save_json

NOTES_PATH = MEMORY_DIR / "notes.json"
_lock = Lock()

_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "it", "for",
         "my", "me", "i", "do", "you", "what", "about", "remember", "note", "that"}


def _load() -> list:
    data = load_json(NOTES_PATH, [])
    return data if isinstance(data, list) else []


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{2,}", text.lower()) if w not in _STOP and len(w) >= 3}


def add(text: str, tags: list[str] | None = None) -> dict:
    note = {"id": uuid.uuid4().hex[:8], "ts": datetime.now().isoformat(timespec="seconds"),
            "text": str(text).strip()[:1000], "tags": [t.lower() for t in (tags or [])]}
    with _lock:
        data = _load()
        data.append(note)
        save_json(NOTES_PATH, data)
    return note


def all_notes() -> list:
    return _load()


def delete(note_id: str) -> bool:
    with _lock:
        data = _load()
        kept = [n for n in data if n.get("id") != note_id]
        if len(kept) != len(data):
            save_json(NOTES_PATH, kept)
            return True
    return False


def recent(n: int = 10) -> list:
    return _load()[-n:]


def search(query: str, limit: int = 5) -> list:
    q = _tokens(query)
    if not q:
        return []
    scored = []
    for note in _load():
        toks = _tokens(note.get("text", "")) | set(note.get("tags", []))
        score = len(q & toks)
        if score:
            scored.append((score, note))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [n for _, n in scored[:limit]]


def format_for_prompt(query: str | None = None, n: int = 6) -> str:
    notes = search(query, n) if query else []
    if not notes:
        notes = recent(n)
    if not notes:
        return ""
    lines = ["[REMEMBERED NOTES — things you saved earlier; use them naturally]"]
    for note in notes:
        when = str(note.get("ts", ""))[:10]
        lines.append(f"  - ({when}) {note.get('text', '')}")
    return "\n".join(lines)
