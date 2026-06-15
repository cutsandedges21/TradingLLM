"""Research goals — lightweight, persistent objectives the copilot stays oriented to.

A goal is a question or objective ("decide whether to buy NVDA this month") that
persists across sessions, accumulates evidence as you do analyses, and can be
completed. Active goals are injected into chat context so the assistant keeps the
thread. Stored as memory/goals.json. (Inspired by Vibe-Trading's research-goal runtime.)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from threading import Lock

from trading_llm.core.paths import MEMORY_DIR, load_json, save_json

GOALS_PATH = MEMORY_DIR / "goals.json"
_lock = Lock()


def _load() -> list:
    data = load_json(GOALS_PATH, [])
    return data if isinstance(data, list) else []


def add(title: str) -> dict:
    goal = {"id": uuid.uuid4().hex[:8], "title": str(title).strip()[:300],
            "status": "active", "created": datetime.now().isoformat(timespec="seconds"),
            "evidence": []}
    with _lock:
        data = _load()
        data.append(goal)
        save_json(GOALS_PATH, data)
    return goal


def list_goals(status: str | None = None) -> list:
    data = _load()
    return [g for g in data if status is None or g.get("status") == status]


def active() -> list:
    return list_goals("active")


def _set_status(goal_id: str, status: str) -> bool:
    with _lock:
        data = _load()
        target = None
        for g in data:
            if g.get("id") == goal_id or g.get("title", "").lower() == goal_id.lower():
                target = g
                break
        # if not matched by id/title, fall back to most recent active goal
        if target is None and status != "active":
            actives = [g for g in data if g.get("status") == "active"]
            target = actives[-1] if actives else None
        if target is None:
            return False
        target["status"] = status
        save_json(GOALS_PATH, data)
        return True


def complete(goal_id: str = "") -> bool:
    return _set_status(goal_id, "done")


def abandon(goal_id: str = "") -> bool:
    return _set_status(goal_id, "abandoned")


def add_evidence(goal_id: str, text: str) -> bool:
    with _lock:
        data = _load()
        for g in data:
            if g.get("id") == goal_id:
                g.setdefault("evidence", []).append(
                    {"ts": datetime.now().isoformat(timespec="seconds"), "text": str(text)[:300]})
                save_json(GOALS_PATH, data)
                return True
    return False


def format_for_prompt() -> str:
    goals = active()
    if not goals:
        return ""
    lines = ["[ACTIVE RESEARCH GOALS — keep these in mind; help the user make progress]"]
    for g in goals:
        ev = f" ({len(g.get('evidence', []))} notes of evidence)" if g.get("evidence") else ""
        lines.append(f"  - {g['title']}{ev}")
    return "\n".join(lines)
