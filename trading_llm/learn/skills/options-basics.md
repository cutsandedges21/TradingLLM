---
name: options-basics
title: Options Basics
tags: options, call, put, strike, premium, expiration, leverage, greeks, theta, contract
level: intermediate
summary: Calls vs puts, what you actually pay for, and why options decay.
---
# Options Basics

An **option** is a contract giving you the *right* (not obligation) to buy or sell 100 shares at a fixed **strike** price before an **expiration** date. You pay a **premium** for that right.

- **Call** = the right to **buy** at the strike. You want the stock to go **up**.
- **Put** = the right to **sell** at the strike. You want the stock to go **down**.

**Why people use them:**
- **Leverage**: a small premium controls 100 shares, so gains (and losses) are amplified.
- **Defined risk** (when buying): the most you can lose is the premium you paid.
- **Hedging**: a put acts like insurance on shares you own.

**The catch beginners underestimate — time decay (theta).** An option is a melting ice cube. Every day that passes, all else equal, it loses value, because there's less time for your bet to work. You can be *right about direction* and still lose if it happened too slowly. Most options expire worthless.

**The "greeks"** measure sensitivities: **delta** (move per $1 of stock), **theta** (decay per day), **vega** (sensitivity to volatility), **gamma** (how delta changes). Beginners mostly need to respect delta and theta.

> Options are powerful and unforgiving. Learn them on paper, understand that buying options is a bet on *direction and timing and volatility* at once, and never risk money you can't lose.
