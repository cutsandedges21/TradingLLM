"""Turn a BacktestResult into a plain-English, educational markdown brief.

Deterministic (no LLM) so it's free and instant. Written for a beginner: every
metric gets a short gloss, and the result is always framed against buy & hold.
"""
from __future__ import annotations

from trading_llm.backtest.runner import BacktestResult


def _verdict(m: dict) -> str:
    excess = m.get("excess_return_pct", 0)
    dd = m.get("max_drawdown_pct", 0)
    bh_dd = m.get("buy_hold_max_drawdown_pct", 0)
    if excess > 1 and dd >= bh_dd:
        return ("**Verdict:** it beat buy & hold *and* took less heat along the way — "
                "the rare double win. Still, one symbol over one window isn't proof.")
    if excess > 1:
        return ("**Verdict:** it beat buy & hold on return, but watch the drawdown "
                "(how deep it fell) — more return often comes with more risk.")
    if excess > -1:
        return ("**Verdict:** roughly a tie with buy & hold. The extra trading rarely "
                "earns its keep unless it clearly cuts drawdown.")
    return ("**Verdict:** buy & hold won here. Timing the market with this rule cost "
            "more than it saved — a common, humbling result worth learning from.")


def explain(r: BacktestResult) -> str:
    if not r.ok:
        return f"⚠️ {r.error}"

    m = r.metrics
    params = ", ".join(f"{k}={v}" for k, v in r.params.items()) or "defaults"
    sign = lambda x: f"{x:+.2f}"  # noqa: E731

    return f"""## Backtest — {r.strategy_label} on {r.symbol}

{r.strategy_desc}

**Window:** {r.start_date} → {r.end_date}  ·  {r.n_bars} bars ({r.interval})  ·  params: `{params}`  ·  starting ${m.get('start_equity'):,.0f}

| Metric | Strategy | Buy & Hold | What it means |
|---|---|---|---|
| Total return | {sign(m['total_return_pct'])}% | {sign(m['buy_hold_return_pct'])}% | total gain over the window |
| CAGR | {sign(m['cagr_pct'])}% | — | annualized growth rate |
| Max drawdown | {m['max_drawdown_pct']:.2f}% | {m['buy_hold_max_drawdown_pct']:.2f}% | worst peak-to-trough fall (the pain) |
| Sharpe | {m['sharpe']:.2f} | — | return per unit of risk (>1 is good) |
| Volatility | {m['volatility_pct']:.2f}% | — | how bumpy the ride was (annualized) |
| Time in market | {m['exposure_pct']:.0f}% | 100% | how often the strategy held a position |
| Trades · win rate | {m['n_trades']} · {m['win_rate_pct']:.0f}% | — | number of round trips and % profitable |

Ending balance: **${m.get('final_equity'):,.0f}** vs buy & hold's path on the same ${m.get('start_equity'):,.0f}. Excess return: **{sign(m['excess_return_pct'])}%**.

{_verdict(m)}

> Educational only. Backtests assume you'd have followed the rule perfectly, ignore taxes/slippage beyond a small cost, and one good (or bad) backtest never guarantees the future. Try different periods and symbols before trusting a rule.
"""
