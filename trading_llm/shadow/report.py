"""Render the behavior diagnostics into an educational markdown brief."""
from __future__ import annotations

_SEV = {"high": "🔴", "moderate": "🟠", "low": "🟡"}


def report(p: dict) -> str:
    if not p.get("ok"):
        return f"📋 **Trade review** — {p.get('message', 'No trades to analyze yet.')}"

    pf = p["profit_factor"]
    payoff = p["payoff_ratio"]
    lines = [
        "## Trade review — your shadow account\n",
        f"Based on **{p['n_trips']} closed round-trips** from your journal.\n",
        "| Metric | Value | What it means |",
        "|---|---|---|",
        f"| Win rate | {p['win_rate_pct']:.0f}% | share of trades that made money |",
        f"| Total P&L | ${p['total_pnl']:,.0f} | net result across all closed trades |",
        f"| Avg win / avg loss | ${p['avg_win']:,.0f} / ${abs(p['avg_loss']):,.0f} | size of a typical winner vs loser |",
        f"| Payoff ratio | {payoff if payoff is not None else '∞'} | avg win ÷ avg loss (want ≥ 1) |",
        f"| Profit factor | {pf if pf is not None else '∞'} | gross profit ÷ gross loss (>1 is profitable) |",
        f"| Expectancy | ${p['expectancy']:,.0f} | average profit per trade |",
        f"| Hold: winners / losers | {p['hold_days_winners']:.1f}d / {p['hold_days_losers']:.1f}d | how long you hold each |",
    ]

    biases = p.get("biases", [])
    if biases:
        lines.append("\n### What your trading reveals\n")
        for b in biases:
            tag = _SEV.get(b.get("severity", "moderate"), "🟠")
            lines.append(f"**{tag} {b['name']}** — {b['detail']}")
            lines.append(f"> *Fix:* {b['lesson']}\n")
    else:
        lines.append("\n### What your trading reveals\n")
        lines.append("No major behavioral red flags so far — disciplined holding and a sane payoff ratio. "
                     "Keep journaling your reasoning so it stays that way.\n")

    lines.append("> This mirrors *how* you trade, not whether any single call was right. "
                 "The biggest gains come from fixing repeated mistakes, not finding new tips. "
                 "See the **Trading Psychology** topic in the Library.")
    return "\n".join(lines)
