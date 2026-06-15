"""Challenges — small, motivating goals computed from the account + journal.

Each challenge has a deterministic check over the trader's state and returns a
done flag + progress (0..1), so the UI/chat can show a checklist that nudges
good habits (in the spirit of AI-Trader's challenges).
"""
from __future__ import annotations

from trading_llm.shadow.diagnostics import analyze


def _progress(done_n: float, target: float) -> float:
    return round(min(1.0, done_n / target), 2) if target else 1.0


def evaluate(account: dict | None, trips: list, max_position_usd: float = 2000.0) -> list[dict]:
    profile = analyze(trips)
    n = profile.get("n_trips", 0)
    equity = (account or {}).get("equity") or 0.0
    start = (account or {}).get("portfolio_value") or 100000.0
    within = sum(1 for t in trips if t.qty * t.entry_price <= max_position_usd * 1.05)
    payoff = profile.get("payoff_ratio") if profile.get("ok") else None
    expectancy = profile.get("expectancy", 0) if profile.get("ok") else 0

    defs = [
        {"id": "first_trade", "title": "First Round-Trip",
         "desc": "Open and then close a paper trade.",
         "done": n >= 1, "progress": _progress(min(n, 1), 1)},
        {"id": "ten_trades", "title": "Get Reps In",
         "desc": "Complete 10 closed round-trips.",
         "done": n >= 10, "progress": _progress(n, 10)},
        {"id": "in_budget", "title": "Respect the Budget",
         "desc": f"Keep every trade within your ${max_position_usd:,.0f} per-trade limit.",
         "done": n >= 1 and within == n, "progress": _progress(within, max(n, 1))},
        {"id": "positive_expectancy", "title": "Find an Edge",
         "desc": "Reach positive expectancy over at least 5 trades.",
         "done": n >= 5 and expectancy > 0,
         "progress": _progress(n, 5) if expectancy > 0 else (0.5 if n >= 5 else _progress(n, 5))},
        {"id": "good_payoff", "title": "Let Winners Run",
         "desc": "Get your average win ≥ your average loss (payoff ≥ 1) over 5+ trades.",
         "done": n >= 5 and payoff is not None and payoff >= 1.0,
         "progress": 1.0 if (n >= 5 and payoff is not None and payoff >= 1.0) else _progress(n, 5)},
        {"id": "patience", "title": "Patience Pays",
         "desc": "Average a 3-day-plus hold over 5+ trades — discipline beats churn.",
         "done": n >= 5 and profile.get("avg_hold_days", 0) >= 3,
         "progress": 1.0 if (n >= 5 and profile.get("avg_hold_days", 0) >= 3)
                     else _progress(min(n, 5), 5) * 0.5},
        {"id": "in_profit", "title": "Beat the Bank",
         "desc": "Grow your paper equity above where you started.",
         "done": equity > start, "progress": 1.0 if equity > start else 0.0},
    ]
    for d in defs:
        d["status"] = "✅ done" if d["done"] else f"{int(d['progress'] * 100)}%"
    return defs
