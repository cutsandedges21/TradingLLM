"""Behavior profile + bias diagnostics from closed round-trips.

The 'shadow account' idea (from Vibe-Trading): hold a mirror up to how you actually
trade. We compute win rate, payoff, expectancy, holding behavior, and flag the
classic biases — disposition effect, cutting winners short, overtrading — each
with a concrete, teachable note.
"""
from __future__ import annotations

from statistics import mean

from trading_llm.shadow.trades import RoundTrip


def _safe_mean(xs: list[float]) -> float:
    return float(mean(xs)) if xs else 0.0


def analyze(trips: list[RoundTrip]) -> dict:
    n = len(trips)
    if n == 0:
        return {"ok": False, "n_trips": 0,
                "message": "No closed round-trips yet. Place and then close some paper trades "
                           "(buy, later sell) and I can profile how you trade."}

    wins = [t for t in trips if t.pnl > 0]
    losses = [t for t in trips if t.pnl < 0]
    gross_win = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in losses)  # positive magnitude

    avg_win = _safe_mean([t.pnl for t in wins])
    avg_loss = _safe_mean([t.pnl for t in losses])  # negative
    payoff = (avg_win / abs(avg_loss)) if avg_loss else float("inf")
    expectancy = sum(t.pnl for t in trips) / n
    hold_win = _safe_mean([t.hold_days for t in wins])
    hold_loss = _safe_mean([t.hold_days for t in losses])
    avg_hold = _safe_mean([t.hold_days for t in trips])

    profile = {
        "ok": True,
        "n_trips": n,
        "win_rate_pct": round(len(wins) / n * 100, 1),
        "total_pnl": round(sum(t.pnl for t in trips), 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "payoff_ratio": round(payoff, 2) if payoff != float("inf") else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "expectancy": round(expectancy, 2),
        "avg_hold_days": round(avg_hold, 2),
        "hold_days_winners": round(hold_win, 2),
        "hold_days_losers": round(hold_loss, 2),
    }

    biases = []
    # Disposition effect: holding losers longer than winners.
    if wins and losses and hold_loss > hold_win * 1.3 and (hold_loss - hold_win) > 0.4:
        biases.append({
            "name": "Disposition effect",
            "severity": "high" if hold_loss > hold_win * 2 else "moderate",
            "detail": f"You hold losers ~{hold_loss:.1f} days but winners only ~{hold_win:.1f} days. "
                      "That's the classic mistake — snatching small wins while clinging to losers, "
                      "hoping they come back.",
            "lesson": "Let winners run and cut losers fast — exit on your stop, not your hope.",
        })
    # Cutting winners short / poor payoff.
    if wins and losses and abs(avg_loss) > avg_win * 1.1:
        biases.append({
            "name": "Cutting winners short",
            "severity": "high" if abs(avg_loss) > avg_win * 1.8 else "moderate",
            "detail": f"Your average win is ${avg_win:,.0f} but your average loss is ${abs(avg_loss):,.0f} — "
                      "losses are bigger than wins. Even a good win rate can't survive that.",
            "lesson": "Aim for winners at least as big as your losers (a payoff ratio ≥ 1).",
        })
    # Overtrading / churn: very short holds across many trades.
    if n >= 8 and avg_hold < 1.0:
        biases.append({
            "name": "Overtrading",
            "severity": "moderate",
            "detail": f"Across {n} trades your average hold is under a day. Rapid churn piles up "
                      "spread + slippage costs and is usually driven by boredom or FOMO, not edge.",
            "lesson": "Trade less, but better. Doing nothing is a valid position.",
        })
    # Negative expectancy overall.
    if expectancy < 0:
        biases.append({
            "name": "Negative expectancy",
            "severity": "high",
            "detail": f"On average each trade loses ${abs(expectancy):,.0f}. The current approach "
                      "doesn't have an edge yet — that's normal early on and fixable.",
            "lesson": "Slow down, journal your reasoning, and focus on risk control before frequency.",
        })

    profile["biases"] = biases
    return profile
