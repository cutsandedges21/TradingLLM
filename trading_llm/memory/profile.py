"""Persistent trader profile — who you are as a trader.

Stored as memory/profile.json. This file is never auto-deleted, so the
assistant remembers your risk tolerance, style, and lessons across restarts.
"""
from __future__ import annotations

from datetime import datetime
from threading import Lock

from trading_llm.core.paths import MEMORY_DIR, load_json, save_json

PROFILE_PATH = MEMORY_DIR / "profile.json"
_lock = Lock()

CATEGORIES = ["identity", "risk_profile", "style", "preferences", "lessons"]
_LABELS = {
    "identity": "About the trader",
    "risk_profile": "Risk profile",
    "style": "Trading style",
    "preferences": "Preferences",
    "lessons": "Lessons learned",
}


def _empty() -> dict:
    return {c: {} for c in CATEGORIES}


def load_profile() -> dict:
    data = load_json(PROFILE_PATH, None)
    if not isinstance(data, dict):
        return _empty()
    base = _empty()
    for key, value in data.items():
        if key in CATEGORIES and isinstance(value, dict):
            base[key] = value
    return base


def save_profile(profile: dict) -> None:
    with _lock:
        save_json(PROFILE_PATH, profile)


def update_profile(updates: dict) -> dict:
    """Merge {category: {key: value | {"value": value}}} into the profile."""
    if not isinstance(updates, dict):
        return load_profile()
    profile = load_profile()
    changed = False
    for cat, items in updates.items():
        if cat not in CATEGORIES or not isinstance(items, dict):
            continue
        for key, value in items.items():
            val = value.get("value") if isinstance(value, dict) else value
            if val is None or (isinstance(val, str) and not val.strip()):
                continue
            entry = {"value": str(val).strip()[:400],
                     "updated": datetime.now().strftime("%Y-%m-%d")}
            if profile[cat].get(key, {}).get("value") != entry["value"]:
                profile[cat][key] = entry
                changed = True
    if changed:
        save_profile(profile)
    return profile


def remember(category: str, key: str, value: str) -> str:
    if category not in CATEGORIES:
        category = "preferences"
    update_profile({category: {key: {"value": value}}})
    return f"Saved {category}/{key} = {value}"


def forget(category: str, key: str) -> str:
    profile = load_profile()
    if category in profile and key in profile[category]:
        del profile[category][key]
        save_profile(profile)
        return f"Removed {category}/{key}"
    return f"Not found: {category}/{key}"


def format_profile_for_prompt(profile: dict | None = None) -> str:
    profile = profile if profile is not None else load_profile()
    lines: list[str] = []
    for cat in CATEGORIES:
        items = profile.get(cat, {})
        if not items:
            continue
        lines.append(f"{_LABELS[cat]}:")
        for key, entry in list(items.items())[:12]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ')}: {val}")
    if not lines:
        return ""
    return "[WHAT YOU KNOW ABOUT THIS TRADER — use it naturally]\n" + "\n".join(lines)
