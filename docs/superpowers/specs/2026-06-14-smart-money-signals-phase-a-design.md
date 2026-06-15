# Smart-Money Signals & Market Regime — Phase A Design

**Date:** 2026-06-14
**Status:** Approved (design); implementation pending
**Scope of this doc:** Phase A only. Phases B and C are sketched for context but get their own specs.

---

## Goal & honest framing

The user asked: *"make it so this app can actually give me an edge … learn from what the
richest people in the world are currently trading and how the market moves … I want to be
informed … and run paper tests to see if a trade would work."*

**What we will NOT claim:** a guaranteed edge. The data a free, local app can reach is *public*.
13F institutional holdings are lagged up to 45 days; Form 4 insider filings ~2 days; congressional
disclosures are slow and irregular. Public information is largely priced in. Nothing here promises
profit.

**What we WILL deliver:** turn the app from "reasons over a price snapshot" into "reasons over a
price snapshot **+ market regime + smart-money flows**," surfaced honestly with every filing's date
and lag, and (in later phases) backtestable and trackable in paper. This directly serves *"I want
to be informed."*

This is the **full multi-phase plan**; only Phase A is specified in detail here:

- **Phase A — Inform (this doc):** market-regime detector + unified smart-money signals
  (Form 4 insiders, curated 13F holdings, congress) surfaced in the LLM snapshot, the single-brain
  context, a read API, and a new "Smart Money" UI view.
- **Phase B — Prove (later spec):** event-study backtester — "across all past occurrences of this
  signal, what was the forward 30/60/90-day return vs. the market?" with the same out-of-sample
  honesty as the existing optimizer.
- **Phase C — Act & learn (later spec):** live paper-trade-from-signal + a "Smart-Money Analyst"
  voice in the multi-agent committee + a reflection loop that records post-signal outcomes and feeds
  base rates back.

---

## Constraints (inherited from the project)

- **Local, private, free data only.** No paid feeds, no brokerage signup.
- **Fail-soft everywhere.** A dead/blocked/rate-limited data source must never crash the snapshot,
  the chat, or the UI — it returns empty + a "stale/unavailable" flag.
- **Deterministic, offline tests.** No network in tests; no Playwright (verify via build + curl +
  Python smoke tests). New tests parse from saved local fixture strings.
- **Atomic persistence.** All cache writes go through `core/paths.save_json` (temp-file + replace).
- **Windows / OneDrive aware.** State lives under the repo root (`memory/`), already `.gitignore`d.

---

## Architecture

### New top-level package: `trading_llm/signals/`

Named `signals/` (top level) — deliberately distinct from the existing
`trading_llm/brain/debate/signal.py` (which holds `parse_rating`).

```
trading_llm/signals/
  __init__.py     # exports SignalService, Signal, Regime
  models.py       # Signal, SignalBundle, Regime dataclasses (pure data, no I/O)
  regime.py       # detect_regime(data) -> Regime  (uses bars we already fetch)
  edgar.py        # SEC EDGAR client: Form 4 (insiders) + 13F (curated filers)
  congress.py     # congressional disclosures (degradable; least reliable source)
  service.py      # SignalService: orchestrate sources + regime, disk cache, fail-soft
  format.py       # compact LLM-snapshot lines + structured dicts for the API/UI
```

Each unit has one job, a narrow interface, and is testable in isolation.

#### `models.py` — pure data

```python
@dataclass
class Signal:
    kind: str          # "insider_buy" | "insider_sell" | "inst_13f" | "congress"
    symbol: str
    date: str          # transaction/report date, "YYYY-MM-DD"
    actor: str         # "Jane Doe (CEO)" | "Berkshire Hathaway" | "Sen. John Roe"
    direction: int     # +1 bought/added, -1 sold/trimmed
    size_usd: float    # best-effort notional; 0.0 if unknown (e.g. some 13F holdings)
    detail: str        # short human string
    source_url: str    # link to the SEC/source filing
    as_of: str         # when this datum was fetched, "YYYY-MM-DD"
    lag_note: str      # "~2-day lag" | "~45-day lag (last quarter)" | "varies"

@dataclass
class SignalBundle:
    symbol: str
    signals: list[Signal]
    # aggregates (computed in __post_init__ or a build() classmethod):
    net_insider_usd_30d: float
    net_insider_usd_90d: float
    insider_buys_30d: int
    insider_sells_30d: int
    funds_holding: int           # # of tracked 13F filers currently holding it
    congress_trades_90d: int
    stale: bool                  # true if served from an expired cache
    def summary_line(self) -> str: ...   # delegates to format.py

@dataclass
class Regime:
    label: str         # "risk_on" | "neutral" | "risk_off"
    trend: str         # "up" | "sideways" | "down"
    vol: str           # "low" | "normal" | "high"
    breadth_pct: float # % of universe above 50-day SMA
    spy_vs_200dma_pct: float
    realized_vol_20d: float
    momentum_3m_pct: float
    summary: str       # one human line
    as_of: str
    ok: bool           # false if we couldn't compute (no data) -> snapshot omits it
```

#### `regime.py` — market state from data we already fetch

`detect_regime(data, universe=None) -> Regime`. Inputs are `MarketData.get_bars`:

- **Trend:** SPY last close vs its 200-day SMA → `spy_vs_200dma_pct`; `up` if >+1%, `down` if
  <−1%, else `sideways`.
- **Volatility:** annualized 20-day realized vol of SPY daily returns → `low` (<12%), `normal`
  (12–22%), `high` (>22%). (Thresholds are constants, documented, tunable in settings later.)
- **Breadth:** % of the 40-name factor universe (`factors.runner.DEFAULT_UNIVERSE`, via
  `clean_universe`) trading above their own 50-day SMA.
- **Momentum:** SPY 63-trading-day (~3-month) return.
- **Label rule (deterministic):** `risk_on` when trend `up` AND breadth ≥55% AND vol ≤ `high`;
  `risk_off` when trend `down` OR breadth ≤35% OR vol `high` with negative momentum; else `neutral`.
  Exact thresholds live as module constants so the unit test pins them.
- Pure function of bars → unit-testable with synthetic series. `ok=False` if SPY bars are missing.

#### `edgar.py` — SEC EDGAR (official, free)

SEC fair-access rules: a descriptive `User-Agent` is **required**; keep requests <10/sec.
A shared `_get(url, host)` helper sets the UA, a short timeout, one backoff retry on 429/503, and
returns parsed JSON/text or `None`.

- **Form 4 (insiders):** discover recent Form 4 filings for a ticker via EDGAR (the full-text
  search API at `efts.sec.gov` and/or the per-company submissions feed — the **exact discovery
  endpoint + query params are confirmed during implementation** against live SEC docs, since this is
  the fiddliest external dependency). For each filing, fetch the Form 4 XML and parse
  `nonDerivativeTransaction` rows: transaction code (`P`=open-market purchase → `insider_buy`,
  `S`=sale → `insider_sell`), shares × price → `size_usd`, plus `reportingOwner` name/title. Only
  open-market buys/sells are kept (codes P/S); option exercises and gifts are skipped to avoid
  noise. Returns `list[Signal]`.
- **13F (curated filers):** for each `(cik, name)` in the configured `famous_filers`, fetch their
  most recent 13F-HR via the official submissions API (`data.sec.gov/submissions/CIK##########.json`,
  zero-padded to 10 digits) → locate the latest 13F-HR → fetch + parse its information table (XML)
  into holdings. Phase A surfaces
  **current holdings only** (which tracked funds hold a given symbol); deltas-vs-last-quarter are
  deferred to keep Phase A tight. `size_usd` from the table's `value` field; `direction=+1`.
  CUSIP→ticker mapping: maintain a small local CUSIP→ticker map for the watchlist/universe (13F
  reports CUSIPs, not tickers); unmapped holdings are ignored rather than guessed.
- Parsing functions take a **string** (the fetched XML/JSON) and return `list[Signal]`, so tests
  feed saved fixtures with no network.

#### `congress.py` — congressional disclosures (degradable)

A `fetch_congress(symbol)` over a free public source (House/Senate financial-disclosure dataset /
community mirror). Wrapped so any failure → `[]` + the service marks the source `unavailable`.
Clearly documented as the least-reliable feed. Parsing again takes a string fixture for tests.

#### `service.py` — orchestration, caching, fail-soft

`SignalService(data, settings)`:

- `regime() -> Regime` — cached in memory ~1h; recompute on expiry.
- `signals_for(symbol) -> SignalBundle` — merges Form 4 + 13F + congress for the symbol, builds
  aggregates. Disk-cached under `memory/signals_cache/<symbol>.json` via `paths.save_json`, TTL =
  `signals.cache_ttl_hours` (default 12). On fetch failure, serve the last cached bundle with
  `stale=True`; if no cache exists, return an empty bundle (never raise).
- Each source is called inside its own try/except with a short timeout; the snapshot only ever
  **reads cache** (fast), while refreshes happen on TTL/explicit request — so building the snapshot
  is never blocked on a slow SEC call.

#### `format.py`

- `regime_summary(regime) -> str` — e.g. `Regime: RISK-ON (trend up · breadth 62% · vol normal)`.
- `signals_summary(bundle) -> str` — e.g.
  `insiders: +$2.1M (3 buys/30d) · held by 4 tracked funds · 1 congress trade/90d`.
- `bundle_to_dict` / `regime_to_dict` — JSON for the API/UI, each row carrying `date`, `lag_note`,
  `source_url`.

### Wiring into existing code

- **`market/snapshot.py` → `build_snapshot()`** gains an optional `signal_service` param. When
  present: prepend a `[MARKET REGIME]` line, and append a short smart-money tag under each watchlist
  symbol (read-from-cache only; terse to protect the context budget). Signature stays
  backward-compatible (param defaults to `None` → current behavior).
- **`core/engine.py`:** construct a `SignalService` in `__init__`; add `_signals_context(ticker)`
  (mirrors `_technical_context`/`_news_context`) and include it in the single-brain context block in
  the standard chat path. Pass the service into `build_snapshot(...)`. *(Committee agent + learning =
  Phase C.)*
- **`server.py`:** `GET /api/regime` and `GET /api/signals/{symbol}` returning the `format.py`
  dicts, behind the existing `_api_auth` middleware.
- **UI (`web/`):** new **Smart Money** view (sidebar nav + `View` type + title), code-split via
  `lazy()` like `ChartsPage`/`StudioPage`. Shows the regime banner and per-symbol rows
  (insider / 13F / congress), each row displaying the filing date + lag note + source link. A small
  regime chip is added to `Header`. An explainer card states plainly what regime/signals do and do
  not mean.

### Config (`config/settings.json` → new `signals` block)

```json
"signals": {
  "enabled": true,
  "sec_user_agent": "TradingLLM research sportsdude3133@gmail.com",
  "cache_ttl_hours": 12,
  "sources": { "insiders": true, "institutional_13f": true, "congress": true },
  "famous_filers": [
    { "cik": "0001067983", "name": "Berkshire Hathaway" }
  ]
}
```

`sec_user_agent` is documented as **required by SEC**; `famous_filers` ships with a couple of
well-known CIKs and is user-editable.

---

## Data flow

1. UI/snapshot/engine asks `SignalService.regime()` / `.signals_for(sym)`.
2. Service returns cached data immediately if fresh; otherwise triggers a guarded refresh
   (EDGAR/congress) and updates the disk cache atomically.
3. `format.py` renders compact lines for the LLM and structured dicts for the API/UI.
4. The LLM reasons over regime + signals as **context**; it never receives them as instructions.

---

## Error handling

- **SEC 429 / missing UA:** backoff once, then serve cache + `stale`.
- **Network down / source blocked:** serve last cache; mark `stale`/`unavailable`; UI shows the
  staleness. Snapshot/chat continue unaffected (signals are additive).
- **Unparseable filing / unmapped CUSIP:** skip that record (never guess), keep the rest.
- **No SPY bars:** `Regime.ok=False` → snapshot omits the regime line entirely.

---

## Testing (offline, deterministic — added to `tests/smoke_test.py`)

- `regime.detect_regime` over synthetic bar sets → asserts `risk_on` / `risk_off` / `neutral`
  classification and the computed fields, with thresholds pinned to module constants.
- `models`: `SignalBundle` aggregation (net 30/90d insider $, buy/sell counts, funds_holding).
- `edgar`: `parse_form4(xml_fixture)` and `parse_13f(xml_fixture)` over saved sample strings →
  assert parsed `Signal` fields (no network).
- `congress`: `parse_congress(fixture)` over a saved sample.
- `service`: fail-soft (a source raising → empty/stale bundle, no exception) + cache round-trip via
  a tmp dir; TTL expiry behavior.
- `format`: stable `regime_summary` / `signals_summary` strings.
- snapshot integration: `build_snapshot(..., signal_service=fake)` includes the `[MARKET REGIME]`
  line and a smart-money tag.

Fixtures: small trimmed real Form 4 / 13F info-table / congress samples saved under
`tests/fixtures/signals/`.

---

## Out of scope for Phase A (explicit)

- Event-study or any backtesting of signals (Phase B).
- Live paper-trade-from-signal, the committee "Smart-Money Analyst" agent, and the longitudinal
  learning/base-rate loop (Phase C).
- 13F quarter-over-quarter deltas (deferred; Phase A shows current holdings only).
- A full CUSIP↔ticker database (Phase A uses a small local map covering the universe/watchlist).

---

## Success criteria for Phase A

1. `python tests/smoke_test.py` passes, including all new signal/regime checks.
2. `npm run build` (tsc + vite) passes with the new Smart Money view code-split.
3. With network available, `GET /api/regime` and `GET /api/signals/AAPL` return populated JSON;
   with the sources disabled/offline, they return empty-but-valid JSON (no 500s).
4. The LLM snapshot string contains a `[MARKET REGIME]` line and per-symbol smart-money tags when
   the service has data.
5. Every signal shown in the UI/API carries its filing date + lag note. No signal is framed as a
   trade instruction.
