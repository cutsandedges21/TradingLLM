"""Phase 1 — learn-from-outcomes reflection.

``resolve_pending`` fetches realized return + alpha for past decisions in
``memory.decision_log``, writes a lesson with the Reflector, and persists it so
recent same-ticker decisions + cross-ticker lessons flow into future PM prompts.
All best-effort: missing langchain, no provider, or no network -> no-op.
"""
from __future__ import annotations

import logging

from trading_llm.memory import decision_log
from trading_llm.brain.reflection.outcomes import fetch_returns, resolve_benchmark
from trading_llm.brain.reflection.reflector import Reflector

logger = logging.getLogger(__name__)

__all__ = ["resolve_pending", "Reflector", "fetch_returns", "resolve_benchmark"]


def resolve_pending(router, ticker: str, holding_days: int = 5) -> int:
    """Score + reflect on pending decisions for ``ticker``; persist outcomes.

    Returns the number of entries updated. Never raises — any failure (no
    langchain, no provider, no network, data not ready) leaves entries pending.
    """
    pending = decision_log.get_pending_entries(ticker)
    if not pending:
        return 0

    try:
        llm = router.get_llm("quick")
    except Exception:
        return 0  # no LLM available -> can't reflect yet
    reflector = Reflector(llm)
    benchmark = resolve_benchmark(ticker)

    updates = []
    for entry in pending:
        raw, alpha, days = fetch_returns(ticker, entry["date"],
                                         holding_days=holding_days, benchmark=benchmark)
        if raw is None:
            continue  # outcome not available yet — try again next run
        try:
            reflection = reflector.reflect_on_decision(
                entry.get("decision", ""), raw, alpha, benchmark)
        except Exception as exc:
            logger.warning("Reflection failed for %s %s: %s", ticker, entry["date"], exc)
            continue
        updates.append({
            "ticker": ticker, "trade_date": entry["date"],
            "raw_return": raw, "alpha_return": alpha,
            "holding_days": days, "reflection": reflection,
        })

    return decision_log.batch_update_with_outcomes(updates)
