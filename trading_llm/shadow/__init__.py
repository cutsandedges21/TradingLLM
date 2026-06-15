"""Phase 5 — shadow account: profile how you actually trade, and name the biases.

Loads your paper-trade journal (or an uploaded broker CSV), pairs fills into closed
round-trips, diagnoses behavioral biases (disposition effect, cutting winners short,
overtrading), and explains them. Ported in spirit from Vibe-Trading's shadow account.

    from trading_llm.shadow import review
    print(review()["report"])
"""
from __future__ import annotations

from trading_llm.shadow.trades import load_round_trips, RoundTrip
from trading_llm.shadow.diagnostics import analyze
from trading_llm.shadow.report import report

__all__ = ["review", "load_round_trips", "RoundTrip", "analyze", "report"]


def review(csv_text: str | None = None) -> dict:
    """Full shadow-account review: profile + biases + markdown report."""
    trips = load_round_trips(csv_text)
    profile = analyze(trips)
    return {
        "ok": profile.get("ok", False),
        "profile": profile,
        "report": report(profile),
        "n_trips": profile.get("n_trips", 0),
    }
