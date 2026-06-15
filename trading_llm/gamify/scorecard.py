"""A trader scorecard — turn the paper account + journal into a discipline grade.

Gamification (in the spirit of AI-Trader's challenges/scoring): a single, honest
letter grade built from profitability, edge quality, and discipline, with a
plain-English note per component so the score teaches rather than just judges.
"""
from __future__ import annotations

from trading_llm.shadow.diagnostics import analyze


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _grade(score: float) -> str:
    return ("A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55
            else "D" if score >= 40 else "F")


def scorecard(account: dict | None, trips: list, max_position_usd: float = 2000.0) -> dict:
    profile = analyze(trips)
    if not profile.get("ok"):
        return {"ok": False, "grade": "—", "score": None,
                "message": "No closed trades yet — make a few paper trades and I'll grade your trading."}

    equity = (account or {}).get("equity")
    start = (account or {}).get("portfolio_value") or 100000.0
    # use total realized P&L relative to starting cash as the return proxy
    ret_pct = (profile["total_pnl"] / start * 100) if start else 0.0

    pf = profile.get("profit_factor")
    if pf is not None:
        pf_val = pf
    else:
        # No losses recorded: only "strong" if there were real wins — a flat $0
        # trade shouldn't inflate the grade.
        pf_val = 2.0 if profile["win_rate_pct"] > 0 else 1.0

    # budget adherence: share of trades sized within the per-trade risk budget
    within = sum(1 for t in trips if t.qty * t.entry_price <= max_position_usd * 1.05)
    budget_pct = within / len(trips) * 100 if trips else 100.0
    activity = 100.0 if profile["avg_hold_days"] >= 1.0 else 60.0

    prof = _clamp(50 + ret_pct * 5)
    edge = _clamp(40 + (pf_val - 1) * 60)
    discipline = _clamp(0.7 * budget_pct + 0.3 * activity)

    score = round(0.35 * prof + 0.30 * edge + 0.35 * discipline)
    return {
        "ok": True,
        "score": score,
        "grade": _grade(score),
        "components": [
            {"name": "Profitability", "score": round(prof),
             "note": f"realized P&L ${profile['total_pnl']:,.0f} ({ret_pct:+.1f}% of starting cash)"},
            {"name": "Edge quality", "score": round(edge),
             "note": f"profit factor {pf if pf is not None else '∞'}, payoff {profile.get('payoff_ratio') or '∞'}"},
            {"name": "Discipline", "score": round(discipline),
             "note": f"{budget_pct:.0f}% of trades within budget; avg hold {profile['avg_hold_days']:.1f}d"},
        ],
        "n_trips": profile["n_trips"],
    }
