"""Turn a factor BenchResult into a plain-English, educational markdown brief."""
from __future__ import annotations

from trading_llm.factors.runner import BenchResult

_STRENGTH_EMOJI = {"strong": "🟢", "alive": "🟡", "weak": "⚪"}


def explain(b: BenchResult, top: int = 8) -> str:
    if not b.ok:
        return f"⚠️ {b.error}"

    ranked = [r for r in b.results if r.get("ok")]
    if not ranked:
        return "⚠️ No factor produced a usable signal on this universe/period."

    rows = []
    for r in ranked[:top]:
        tag = _STRENGTH_EMOJI.get(r["strength"], "⚪")
        rows.append(
            f"| {r['label']} | {r['category']} | {r['ic_mean']:+.4f} | {r['ir']:+.2f} | "
            f"{r['ic_positive_pct']:.0f}% | {r['spread_pct']:+.2f}% | {tag} {r['strength']} ({r['direction']}) |"
        )

    best = ranked[0]
    uni = ", ".join(b.universe[:8]) + (f" +{len(b.universe) - 8} more" if len(b.universe) > 8 else "")

    return f"""## Factor scan — which alphas worked

**Universe:** {b.n_symbols} names ({uni})
**Window:** {b.start_date} → {b.end_date} · {b.n_days} bars · forward horizon: {b.horizon} days

Each factor ranks the universe every day; **IC** (information coefficient) is how well that ranking lined up with the *next {b.horizon} days'* returns. **IR** = IC mean ÷ IC std (consistency). Positive IC ⇒ the signal points the right way; negative ⇒ it's a reversal (fade it).

| Factor | Type | IC mean | IR | IC > 0 | Top−Bottom | Read |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

**Best on this window:** {best['label']} — {best['description']} It scored an IC of **{best['ic_mean']:+.4f}** (IR {best['ir']:+.2f}), with top-ranked names beating the bottom by **{best['spread_pct']:+.2f}%** over {b.horizon} days on average.

**How to read this:**
- IC around **±0.03+** with **IR ±0.3+** is a genuinely useful signal; most real factors live near ±0.01–0.05. Tiny ICs are mostly noise.
- A **negative** IC isn't useless — it's a *reversal* signal (rank it the other way).
- "Top−Bottom" is the average forward-return gap between the highest- and lowest-ranked names — the intuitive payoff.

> Educational only. One universe over one window is *not* proof a factor works — IC is unstable, decays, and crowds out. Re-run on different baskets and periods, and never size a real trade off a single scan.
"""
