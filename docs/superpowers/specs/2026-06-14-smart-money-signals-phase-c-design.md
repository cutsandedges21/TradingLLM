# Smart-Money Signals — Phase C Design (Act & Learn)

**Date:** 2026-06-14
**Status:** Approved (final phase of the A→B→C arc). A (Inform) + B (Prove) shipped.
**Goal:** Let the app *act* on fresh smart-money signals in paper, give the committee a
**Smart-Money Analyst** voice, and **learn** from what actually happened after each
signal-driven decision — closing the loop honestly (base rates, not promises).

## Three pieces

### C1 — Smart-Money Analyst in the committee
A new analyst voice alongside the technical + news analysts in the multi-agent debate.
- `prompts.smart_money_analyst_prompt(ticker, signals_context)` — grounded (only the provided
  regime + insider/13F/congress + event-study edge + track record), with the same teach + honesty rules.
- `agents.run_smart_money_analyst(llm, ticker, signals_context)`.
- `pipeline`: run as analyst #3 → `DebateResult.smart_money_report`; include it in the bull/bear
  resources and the Portfolio Manager prompt; emit a progress stage; add to transcript + markdown.
- `debate.run(..., signals_context="")` — new optional arg (backward compatible).
- `engine._run_debate` builds a rich `signals_context`: regime summary + the symbol's signal bundle
  + the event-study edge (cached) + the learning track record, and passes it in.

### C2 — Paper-trade-from-signal (act)
- `engine.signal_ideas(limit=8)` — scan watchlist + factor universe (cached bundles only, non-blocking)
  for **fresh actionable longs**: net positive insider $ over 30d with ≥1 buy. Score by net insider $
  (boosted when regime is risk-on). Return ranked ideas: `{symbol, side:"buy", notional, score,
  rationale, regime_label, net_insider_30d, buys_30d}`. Sizing = a fraction of `risk.max_position_usd`.
- `GET /api/signals/ideas`.
- Acting reuses the existing trade flow: the UI opens the standard confirm dialog with the proposal;
  the proposal carries `source:"signal_idea"` + signal metadata. `engine.place_trade` detects that and
  records the trade to the **signal journal** (C3) so its outcome can be attributed later.
- Honesty: ideas are *candidates to consider*, sized small, paper only, never auto-executed; the
  rationale states the signal is public + lagged.

### C3 — Learning loop
`trading_llm/signals/learning.py` + `memory/signal_journal.json` (atomic writes):
- `record(symbol, kind, regime_label, decision_date, ref_price, side, note)` — append a pending entry.
- `resolve_pending(horizon_days=60)` — for entries older than the horizon, use
  `reflection.outcomes.fetch_returns` to get raw + **alpha vs SPY**, mark win = alpha>0. Idempotent.
- `base_rates()` — aggregate overall and by `(kind, regime_label)`: n, win_rate, avg_alpha.
- `track_record_context()` — a compact string ("insider-buy ideas in risk-on: 6/9 beat SPY, avg
  +2.1% alpha") fed into the Smart-Money Analyst prompt **and** surfaced in the UI.
- `engine` resolves pending lazily (best-effort) on regime()/ideas() calls. `GET /api/signals/track-record`.

## UI (Smart Money page)
- **Actionable now** section: ranked signal ideas, each with a "Paper-trade" button → existing
  confirm dialog. Empty state when nothing is actionable.
- **Track record** card: base-rate table from the learning loop (overall + by regime), with the
  honest caveat that it's a tiny, young sample.

## Error handling / honesty
All scans are cache-only + fail-soft (never block). Ideas are never auto-traded. Base rates show n
and warn when small. Everything stays paper; signals remain "context," not advice.

## Testing (offline, deterministic)
- `run_smart_money_analyst` with a **fake LLM** (echoes prompt) → asserts the signals context reaches
  the model and the pipeline includes the report (mirrors existing `test_debate_pipeline`).
- `learning`: record → resolve (monkeypatched fetch_returns) → base_rates math + win_rate + context string.
- `signal_ideas`: with a fake service returning crafted bundles → asserts ranking + sizing + rationale.
- Added to `tests/smoke_test.py`.

## Out of scope
Real-broker execution (still mock/paper by default + the existing mandate guard for opt-in Alpaca).
No auto-trading. No ML training — "learning" = the reflection/base-rate loop.
