"""Phase 1 — multi-agent debate (ported from TradingAgents, grounded on our data).

The analyst -> bull/bear -> trader -> risk-debate -> portfolio-manager pipeline,
driven by ``ProviderRouter.get_llm()``. Wired into ``TradingEngine`` for
"deep analysis" requests; the transcript is surfaced as a teaching artifact.
"""

from trading_llm.brain.debate.pipeline import DebateEngine, DebateResult
from trading_llm.brain.debate.signal import parse_rating, rating_to_proposal

__all__ = ["DebateEngine", "DebateResult", "parse_rating", "rating_to_proposal"]
