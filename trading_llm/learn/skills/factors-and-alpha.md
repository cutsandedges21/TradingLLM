---
name: factors-and-alpha
title: Factors, Alpha & the IC
tags: factor, alpha, momentum, reversal, value, ic, information coefficient, quant, cross sectional, signal
level: intermediate
summary: What a "factor" is, the momentum vs reversal split, and how the IC measures whether a signal works.
---
# Factors, Alpha & the IC

A **factor** (or **alpha**) is a rule that *ranks* a group of stocks by some characteristic, betting that the ranking predicts future returns. Buy the top of the ranking, avoid/short the bottom.

**The classic factor families:**
- **Momentum**: recent winners keep winning (over months). One of the most robust effects in finance — but it crashes hard at reversals.
- **Reversal**: recent *losers* bounce (over days to weeks). The short-term opposite of momentum.
- **Value**: cheap stocks (low price vs fundamentals) beat expensive ones over long horizons.
- **Low volatility**: calmer stocks have historically delivered better risk-adjusted returns — the "low-vol anomaly."
- **Quality / size**: profitable, stable (or small) companies as a tilt.

**How you measure if a factor "works" — the IC (Information Coefficient):** each day, correlate the factor's *ranking* with the *next few days' returns*. Average that correlation over time:
- **IC ≈ 0** → the ranking is noise.
- **IC around ±0.03** with a decent **IR** (IC mean ÷ IC std = consistency) is a genuinely useful real-world signal. Most real factors are this small — tiny edges, repeated.
- A **negative** IC isn't useless — it's a *reversal* signal; just rank it the other way.

**The hard truths:** factor edges are small, unstable, decay as they get crowded, and can be negative for long stretches. Quant investing is about combining many weak-but-real signals with strict risk control — not finding one magic formula.

> This app's factor scan computes the IC/IR for a zoo of factors (classic + Kakushadze alpha101) over a live universe — try "which alpha factors work best?" to see real, humbling numbers.
