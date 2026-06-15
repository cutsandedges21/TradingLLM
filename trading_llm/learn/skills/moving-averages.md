---
name: moving-averages
title: Moving Averages & Crossovers
tags: sma, ema, moving average, crossover, golden cross, death cross, trend, 50 200, mean
level: beginner
summary: SMA vs EMA, what the slope tells you, and how crossovers signal trend changes.
---
# Moving Averages & Crossovers

A **moving average (MA)** smooths price into a line so you can see the trend through the noise.

- **SMA** (simple) = the plain average of the last N closes. Steady, slower to react.
- **EMA** (exponential) = weights recent prices more, so it turns faster.

**Reading them:**
- Price **above** a rising MA = uptrend; **below** a falling MA = downtrend.
- The **slope** matters more than the exact value — a flat MA means no trend (chop).

**Crossovers** are the classic signal:
- **Golden cross**: a fast MA (e.g. 50-day) crosses *above* a slow one (200-day) → bullish regime.
- **Death cross**: fast crosses *below* slow → bearish regime.
- A 20/50 crossover reacts sooner (more signals, more false alarms); 50/200 is slower but cleaner.

**The catch:** MAs *lag* — they confirm a trend after it's underway and whipsaw badly in sideways markets, firing buy/sell signals that immediately reverse. They shine in trending markets and frustrate you in choppy ones.

> You can backtest any crossover in this app — try "backtest a 20/50 SMA crossover on AAPL" and compare it to buy & hold. The result is often humbling, which is the lesson.
