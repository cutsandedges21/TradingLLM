---
name: macd
title: MACD — Momentum & Trend
tags: macd, histogram, signal line, momentum, trend, crossover, convergence divergence, ema
level: beginner
summary: How the MACD line, signal line, and histogram reveal momentum shifts.
---
# MACD — Moving Average Convergence Divergence

MACD turns two EMAs into a momentum reading. Three pieces:

1. **MACD line** = fast EMA (12) − slow EMA (26). Positive = short-term momentum is stronger than longer-term (bullish); negative = bearish.
2. **Signal line** = a 9-period EMA of the MACD line — a smoothed version.
3. **Histogram** = MACD line − signal line. It's the bars you see; it shows momentum *building or fading*.

**Reading it:**
- **MACD crosses above its signal line** → momentum turning up (a common buy cue).
- **Crosses below** → momentum turning down.
- **Histogram growing** = trend accelerating; **shrinking** = trend tiring even before a crossover.
- **Zero line**: MACD crossing above 0 confirms the faster EMA overtook the slower — a trend shift.

**Honest limits:** like all moving-average tools, MACD lags and chops in sideways markets. It's a momentum *confirmation* tool, best paired with trend context — not a standalone oracle.

> The app computes MACD locally for your watchlist, and the "MACD momentum" backtest strategy lets you test the "long while histogram > 0" rule on any symbol.
