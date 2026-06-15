"""Serves the from-zero 'Learn to Trade' guide that ships with the app."""
from __future__ import annotations

from trading_llm.core.paths import LEARN_PATH


def learn_markdown() -> str:
    """Return the full LEARN_TO_TRADE.md guide (rendered in the Learn tab)."""
    try:
        return LEARN_PATH.read_text(encoding="utf-8")
    except Exception:
        return "LEARN_TO_TRADE.md not found."
