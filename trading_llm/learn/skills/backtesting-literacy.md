---
name: backtesting-literacy
title: How to Read a Backtest
tags: backtest, overfitting, drawdown, sharpe, cagr, curve fitting, lookahead, benchmark, returns
level: intermediate
summary: What a backtest can and can't tell you — and the traps (overfitting, look-ahead) that fool beginners.
---
# How to Read a Backtest

A **backtest** runs a trading rule over historical data to see how it *would have* done. It's the single best way to pressure-test an idea — and the single easiest way to lie to yourself.

**The metrics that matter:**
- **Total return / CAGR**: the headline gain, and its annualized rate. Always compare to **buy & hold** — beating "do nothing" is the bar.
- **Max drawdown**: the worst peak-to-trough fall. This is the *pain* — would you have stuck with it through a −30% stretch? Most people wouldn't.
- **Sharpe ratio**: return per unit of risk. Above ~1 is good; it rewards smooth gains over wild ones.
- **Win rate + number of trades**: a 40% win rate can still be very profitable if winners are bigger than losers.

**The traps that make backtests lie:**
- **Overfitting (curve-fitting)**: tweaking parameters until the rule looks perfect *on the past*. A strategy tuned to fit history usually falls apart live. If 20/50 "works" but 19/48 and 22/55 don't, you've fit noise.
- **Look-ahead bias**: accidentally using information you wouldn't have had in real time (e.g. today's close to decide today's trade). This app shifts signals by one bar to prevent it.
- **Survivorship & costs**: ignoring delisted losers, or assuming free, instant fills, inflates results.
- **One lucky window**: a result on one symbol over one period is an anecdote, not evidence.

**How to use one honestly:** test the *same* rule across several symbols and time windows. If it only works on one cherry-picked case, it doesn't work. Treat a good backtest as "worth investigating," never "proven."

> This app's backtester models a small trading cost, bans look-ahead, and always shows you buy & hold + drawdown — so the numbers stay honest.
