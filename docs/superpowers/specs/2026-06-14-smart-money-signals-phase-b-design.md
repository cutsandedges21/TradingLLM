# Smart-Money Signals — Phase B Design (Prove)

**Date:** 2026-06-14
**Status:** Approved (continues the A→B→C plan); Phase A shipped.
**Goal:** Prove whether a smart-money signal has *historically* paid off — an event
study with honest statistics — so the user can trust (or distrust) a signal before acting.

## The question
"Across every past occurrence of signal X on this symbol, what was the forward
30/60/90-day return, and was it better than just owning the stock / the market?"

## Honesty model (the heart of Phase B)
Raw forward returns lie by omission. We report, per horizon:
- **mean forward return** (raw) and **mean forward alpha** (vs SPY over the same window).
- **unconditional baseline alpha** — average forward alpha over *all* trading days in the
  window. The signal's real **edge = event-alpha − baseline-alpha** (strips the stock's normal drift).
- **hit rate** — % of events with positive alpha.
- **t-stat** of event alpha vs 0 → a verdict: too few events / indistinguishable from noise /
  historically positive / historically negative. Past ≠ future, stated plainly.
- **in-sample vs out-of-sample** — split events chronologically (70/30); did the effect hold in
  recent events or only old ones? Mirrors the optimizer's OOS discipline.

## Scope
- Event sources: insider **buys** and **sells** (Form 4 codes P/S). Freshest + most numerous.
  13F (quarterly, position-level) and congress (unavailable) are out of scope for B.
- Per-symbol study. The stats engine is **pure** so cross-symbol pooling drops in later.

## Architecture
`trading_llm/signals/eventstudy.py` (pure + testable):
- `forward_return(dates_sorted, closes, event_date, horizon_days)` — snap event to next trading
  day, return exit/entry−1 over the horizon. `None` if not enough history.
- `baseline_alpha(dates, closes, spy, horizon)` — mean forward alpha over all eligible days.
- `event_study(events, closes, spy, horizons)` → per-horizon dict (n, mean_ret, mean_alpha,
  baseline_alpha, edge, hit_rate, t_stat, is_alpha, oos_alpha, n_is, n_oos) + an overall verdict.
- `explain(result)` — plain-English summary with the caveats.

Impure wiring:
- `edgar.fetch_insider_signals(..., lookback_days=1095, max_filings=300)` already supports a longer
  window — Phase B calls it for ~3y of events (bounded by what EDGAR `recent` holds; window is
  reported honestly).
- `SignalService.study_signal(symbol, kind, horizons)` — gather events (cached `insider_hist_<SYM>`),
  fetch the symbol + SPY daily closes via `data.get_ohlc`, run `event_study`, return dict. Fail-soft.
- `engine.signal_study(symbol, kind)` → dict; `GET /api/signals/study/{symbol}?kind=insider_buy`.
- UI: a "Does this signal work?" card on the **Smart Money** page — pick buy/sell, run, show the
  per-horizon table + verdict + caveats.

## Error handling
No events / no price history → `ok=False` with a clear message (UI shows "not enough history").
Small samples (n<10) → flagged, never hidden. All network fail-soft.

## Testing (offline, deterministic)
Synthetic price series + hand-built events:
- a constructed "signal that works" (price reliably rises after events) → positive edge, t>2.
- a "signal that doesn't" (random) → edge ≈ 0, verdict "noise".
- forward_return snapping + insufficient-history `None`.
- IS/OOS split counts. Added to `tests/smoke_test.py`.

## Out of scope (→ Phase C)
Acting on live signals in paper, the committee agent, and the longitudinal learning loop.
