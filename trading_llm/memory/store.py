"""Single import surface for the memory layer.

Centralizes the three persistent stores so engine code and later phases import
one place:

    from trading_llm.memory import store
    store.journal.add_entry(...)
    store.profile.update_profile(...)
    store.decision_log.store_decision(...)

The data files all live under ``store.MEMORY_DIR`` (repo-root ``memory/``).
"""
from __future__ import annotations

from trading_llm.core.paths import MEMORY_DIR
from trading_llm.memory import profile, journal, decision_log

__all__ = ["MEMORY_DIR", "profile", "journal", "decision_log"]
