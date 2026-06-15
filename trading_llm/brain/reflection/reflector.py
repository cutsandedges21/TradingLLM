"""Reflector — writes a short lesson from a past decision now that the outcome is known.

Ported from TradingAgents' Reflector: 2-4 plain-prose sentences, compact enough to
re-inject into future Portfolio Manager prompts without bloating context.
"""
from __future__ import annotations

_LOG_REFLECTION_PROMPT = (
    "You are a trading analyst reviewing your own past decision now that the outcome is known.\n"
    "Write exactly 2-4 sentences of plain prose (no bullets, no headers, no markdown).\n\n"
    "Cover in order:\n"
    "1. Was the directional call correct? (cite the alpha figure)\n"
    "2. Which part of the thesis held or failed?\n"
    "3. One concrete lesson to apply to the next similar analysis.\n\n"
    "Be specific and terse. Your output is stored verbatim in a decision log and "
    "re-read by future analysts, so every word must earn its place."
)


class Reflector:
    """Single reflection call over a known outcome."""

    def __init__(self, llm):
        self.llm = llm

    def reflect_on_decision(self, final_decision: str, raw_return: float,
                            alpha_return: float, benchmark: str = "SPY") -> str:
        messages = [
            ("system", _LOG_REFLECTION_PROMPT),
            ("human",
             f"Raw return: {raw_return:+.1%}\n"
             f"Alpha vs {benchmark}: {alpha_return:+.1%}\n\n"
             f"Final Decision:\n{final_decision}"),
        ]
        resp = self.llm.invoke(messages)
        content = getattr(resp, "content", None)
        return (content if isinstance(content, str) else str(resp)).strip()
