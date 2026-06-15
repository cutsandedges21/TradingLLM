"""Persistence for alert rules — atomic JSON on disk, with a couple of starter presets."""
from __future__ import annotations

import uuid
from datetime import datetime
from threading import Lock

from trading_llm.core.paths import MEMORY_DIR, load_json, save_json

RULES_PATH = MEMORY_DIR / "alert_rules.json"
_lock = Lock()

# Shipped presets (disabled by default) so the UI isn't empty.
PRESETS = [
    {"name": "Oversold pullback in an uptrend", "scope": "universe",
     "conditions": [{"field": "rsi", "op": "<=", "value": 35},
                    {"field": "trend", "op": "==", "value": "up"}],
     "action": "buy", "hold_days": 20, "risk_pct": 0.01, "enabled": False},
    {"name": "High composite in a risk-on regime", "scope": "universe",
     "conditions": [{"field": "composite", "op": ">=", "value": 62},
                    {"field": "regime", "op": "==", "value": "risk_on"}],
     "action": "buy", "hold_days": 20, "risk_pct": 0.01, "enabled": False},
    {"name": "Insider buying + above the 200-day", "scope": "universe",
     "conditions": [{"field": "insider_buys_30d", "op": ">=", "value": 1},
                    {"field": "price_vs_sma200_pct", "op": ">", "value": 0}],
     "action": "buy", "hold_days": 30, "risk_pct": 0.01, "enabled": False},
]


def _load() -> list:
    data = load_json(RULES_PATH, None)
    if data is None:
        seeded = [{**p, "id": uuid.uuid4().hex[:8],
                   "created": datetime.now().strftime("%Y-%m-%d")} for p in PRESETS]
        save_json(RULES_PATH, seeded)
        return seeded
    return data if isinstance(data, list) else []


def list_rules() -> list:
    return _load()


def save_rule(rule: dict) -> dict:
    with _lock:
        rules = _load()
        rid = rule.get("id")
        if rid:
            for i, r in enumerate(rules):
                if r.get("id") == rid:
                    rules[i] = {**r, **rule}
                    save_json(RULES_PATH, rules)
                    return rules[i]
        rule = {**rule, "id": uuid.uuid4().hex[:8],
                "created": datetime.now().strftime("%Y-%m-%d")}
        rules.append(rule)
        save_json(RULES_PATH, rules)
        return rule


def delete_rule(rid: str) -> bool:
    with _lock:
        rules = _load()
        new = [r for r in rules if r.get("id") != rid]
        if len(new) != len(rules):
            save_json(RULES_PATH, new)
            return True
        return False
