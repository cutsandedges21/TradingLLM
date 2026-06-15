"""Phase 5 — gamification: a discipline scorecard + challenges that nudge good habits.

    from trading_llm.gamify import coach_report, scorecard, challenges
"""
from __future__ import annotations

from trading_llm.gamify.scorecard import scorecard
from trading_llm.gamify.challenges import evaluate as challenges

__all__ = ["scorecard", "challenges", "coach_report"]

_GRADE_EMOJI = {"A": "🏆", "B": "🟢", "C": "🟡", "D": "🟠", "F": "🔴", "—": "⚪"}


def coach_report(account: dict | None, trips: list, max_position_usd: float = 2000.0) -> str:
    sc = scorecard(account, trips, max_position_usd)
    chs = challenges(account, trips, max_position_usd)
    lines = ["## Your trading coach\n"]

    if sc.get("ok"):
        emoji = _GRADE_EMOJI.get(sc["grade"], "⚪")
        lines.append(f"### {emoji} Grade: {sc['grade']}  ·  {sc['score']}/100")
        lines.append(f"<sub>across {sc['n_trips']} closed trades</sub>\n")
        lines.append("| Component | Score | Note |")
        lines.append("|---|---|---|")
        for c in sc["components"]:
            lines.append(f"| {c['name']} | {c['score']}/100 | {c['note']} |")
        lines.append("")
    else:
        lines.append(f"_{sc.get('message', 'No trades graded yet.')}_\n")

    done = sum(1 for c in chs if c["done"])
    lines.append(f"### 🎯 Challenges ({done}/{len(chs)} complete)\n")
    for c in chs:
        mark = "✅" if c["done"] else "⬜"
        prog = "" if c["done"] else f"  ·  *{int(c['progress'] * 100)}%*"
        lines.append(f"{mark} **{c['title']}** — {c['desc']}{prog}")

    lines.append("\n> Discipline beats prediction. These nudge the habits that actually compound — "
                 "sizing, patience, and letting winners run. It's all paper, so practice freely.")
    return "\n".join(lines)
