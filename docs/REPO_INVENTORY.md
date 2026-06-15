# Portability Inventory — what's reusable from the 5 repos

Goal: redesign **Trading LLM** into a **local, educational, paper-only quant-research
workstation** — Vibe-Trading-level capability, TradingAgents-style reasoning,
freqtrade/nautilus-grade backtesting, with a strong "teach the user trading" layer.

Legend: ⭐ = take it (high value, portable) · ◑ = borrow design/parts · ✕ = skip / out of scope

---

## 1. TradingAgents (Python · LangGraph) — the *reasoning brain*

Clean, modular, self-contained `tradingagents/` package. Best single thing to adopt
**wholesale** as the deep-analysis engine: call `propagate(ticker, date) -> (state, decision)`.

| Module | What it is | Verdict |
|---|---|---|
| `graph/` (trading_graph, setup, conditional_logic, propagation, signal_processing) | Multi-agent debate pipeline: analysts → bull/bear researchers → trader → 3-way risk debate → portfolio manager → BUY/SELL/HOLD | ⭐ adopt |
| `graph/reflection.py` + `agents/utils/memory.py` (`TradingMemoryLog`) | Learn-from-outcomes loop: logs each decision, later fetches realized return + alpha vs benchmark, writes a 2–4 sentence reflection, re-injects past lessons into future prompts | ⭐ adopt (this is the "learns over time" you already want) |
| `agents/analysts/*` (market, news, social, sentiment, fundamentals) | Prompt-driven analyst nodes, each with its own tools | ⭐ adopt |
| `agents/researchers/*`, `agents/risk_mgmt/*`, `agents/trader/*`, `managers/*` | Bull/bear debate, 3-way risk debate, trader, research+portfolio managers | ⭐ adopt |
| `llm_clients/` (factory: OpenAI/Google/Anthropic/Azure) | Multi-provider LangChain client factory | ◑ overlaps your `llm/brain.py`; reconcile |
| `dataflows/` (yfinance, alpha_vantage, reddit, stocktwits, stockstats) | Data adapters incl. social sentiment | ◑ overlaps your `market/`; cherry-pick sentiment/news |
| `cli/` | Rich terminal UI | ◑ ideas only |

**Deps added:** `langgraph`, `langchain`, `stockstats`. **Effort to reuse:** LOW — it already
exposes a clean entry point.

---

## 2. Vibe-Trading (FastAPI + React 19 · same stack as us) — the *capability superset*

Biggest prize and the closest architectural sibling. Internally coupled (imports like
`from backtest...`, `from src...`), so port **subsystems**, fixing import paths.

| Subsystem | What it is | Verdict |
|---|---|---|
| `agent/backtest/` | Bar-by-bar backtest engine + market engines (crypto/equity/futures/forex/composite/options) + loaders (yfinance/ccxt/okx/akshare/tushare/futu/mootdx) + optimizers (mean-variance/risk-parity/equal-vol/max-div) + metrics + validation + run cards + benchmark + correlation | ⭐ port (lighter than freqtrade's) |
| `agent/src/factors/` + `factors/zoo/` | **452 quant alpha factors** (qlib158 + alpha101 + gtja191 + Fama-French/Carhart) + IC/IR bench runner + registry | ⭐ port (quant + educational gold) |
| `agent/src/skills/` (77 finance skill packs) | Markdown knowledge packs: data-routing, candlestick, ichimoku, elliott, smc, multi-factor, options, macro, valuation, dividend, crypto-derivatives, behavioral-finance, … (pure md + scripts) | ⭐ port — **directly powers the "teach the user" layer** |
| `agent/src/shadow_account/` | Parse YOUR real broker journal → profile behavior biases (disposition, overtrading, anchoring) → extract rules → backtest the "shadow" → HTML/PDF report | ⭐ port (huge educational value) |
| `agent/src/agent/` (loop, tools, context, skills, memory, trace, progress) | Tool-calling agent loop (1014 LOC) + clean `BaseTool`/`ToolRegistry` + context compression + tracing | ⭐ adopt tool pattern; ◑ the loop (vs TradingAgents graph) |
| `agent/src/memory/persistent.py` | Cross-session persistent memory store | ⭐ port (upgrades your JSON journal) |
| `agent/src/session/` | Session store + FTS5 full-text search + SSE events | ◑ port if we keep multi-session chat |
| `agent/src/live/` | Broker connectors + **mandate / order-guard / audit / kill-switch / flatten** safety model for bounded autonomy | ◑ keep the *safety model*; brokers off by default (we're paper-only) |
| `agent/src/goal/`, `hypotheses/` | Research-goal runtime + hypothesis registry | ◑ nice-to-have research spine |
| Strategy export (`pine-script`, `vnpy-export`, MT5/TDX skills) | Export strategies to TradingView/MetaTrader/通达信 | ◑ later |
| `frontend/` (React 19 + Vite) | Full web UI (chat, backtest views, alpha zoo, correlation heatmap, settings) | ◑ reference/borrow components for our `web/` |
| `agent/src/providers/` | LangChain provider abstraction | ◑ overlaps your Brain |
| MCP server (`vibe-trading-mcp`) | Expose tools to other agents | ◑ later |

**Deps added:** heavy — `langchain`, `pandas`, `numpy`, `pandas-ta`/`stockstats`, many optional
data libs. **Effort:** MEDIUM per subsystem (decouple import paths).

---

## 3. AI-Trader (FastAPI + React) — the *gamified practice layer*

A hosted social/copy-trading **platform** (ai4trade.ai). As a local library its code is LOW
portability, but several **concepts/components** are great for an educational app.

| Piece | What it is | Verdict |
|---|---|---|
| `service/server/challenges.py`, `challenge_scoring.py`, `experiments.py`, `rewards.py` | Gamified challenges/competitions, mark-to-market scoring, points/rewards | ◑ borrow — "practice & compete vs benchmark / your past self" is strong *teaching* |
| `service/server/` paper trading + `fees.py` | $100k paper engine with a fee/slippage model | ◑ borrow fee model (improves your `paper_broker.py`) |
| `price_fetcher.py` | Alpha Vantage → yfinance fallback | ◑ overlaps your `market/data.py` |
| `skills/polymarket/` | Prediction-market paper trading | ✕ out of scope (for now) |
| `skills/copytrade`, `tradesync`, signals, leaderboards | Social copy-trading / signal sharing | ✕ needs a hosted platform — skip for local |

**Effort:** borrow concepts, not code.

---

## 4. freqtrade (Python · ccxt) — the *strategy & optimization reference*

Mature **rule-based** bot. Deeply interlinked internally → hard to extract piecemeal.
Best used as a **design reference**, or run standalone as an external crypto engine.

| Piece | What it is | Verdict |
|---|---|---|
| `strategy/interface.py` (`IStrategy`) | Canonical "strategy as a class": `populate_indicators / entry_trend / exit_trend`, ROI table, stoploss, trailing, hyperparameters | ◑ borrow the *contract* for our strategy format |
| `optimize/backtesting.py` + hyperopt (`strategy/hyper.py`, `parameters.py`) | Backtesting + **hyperparameter optimization** (Optuna) | ◑ borrow the hyperopt concept; Vibe's engine for execution |
| `exchange/` (ccxt) | Many crypto exchange connectors | ◑ only if we add live crypto data |
| `freqai/` | ML strategy add-on | ◑ later |
| `rpc/` (Telegram, FreqUI, webserver) | Bot control surfaces | ✕ skip |

**Effort to extract code:** HIGH (tight coupling). **Recommendation:** mine the design;
optionally shell out to freqtrade for serious crypto backtests/hyperopt later.

---

## 5. nautilus_trader (Rust core + Python) — the *pro engine (optional, later)*

Production event-driven engine. Requires building Rust; very heavy. Overkill for a local
educational paper app.

| Piece | What it is | Verdict |
|---|---|---|
| `crates/backtest`, `crates/execution` | Tick-level, realistic fills/slippage, order types | ◑ borrow *fill-realism concepts* for our paper broker |
| `crates/indicators` (also Python `indicators/`) | Large indicator library | ◑ ideas only (you compute indicators locally already) |
| Live adapters | Real exchange/broker live trading | ✕ out of scope |

**Verdict:** ✕ don't port code now. Keep as an optional "pro backtest engine" upgrade later.

---

## Recommendation (evidence-based)

A **redesign of your codebase with heavy reuse**, layered:

1. **Reasoning core** → adopt **TradingAgents** wholesale (debate + reflection-learning).
2. **Quant core** → port **Vibe-Trading** `backtest/` + `factors/` (alpha zoo).
3. **Teaching layer** → port **Vibe** `skills/` (77 finance packs) + `shadow_account/`,
   plus **AI-Trader's** gamified **challenges/scoring** ("learn by practicing & competing").
4. **Data + memory** → keep your free-data ethos; upgrade memory with Vibe's
   `persistent.py`; improve `paper_broker.py` fills with AI-Trader's fee model + nautilus ideas.
5. **Strategy format** → borrow **freqtrade's** `IStrategy` contract + hyperopt concept.
6. **Safety** → paper-only by default; keep Vibe's mandate/kill-switch model dormant for any
   future opt-in broker. **nautilus** stays an optional future upgrade.

Map to strategy choice: this is **"Redesign + heavy reuse"** — your project, redesigned, with
the strongest parts of all 5 pulled in (and the parts that don't fit a local educational tool
explicitly left out).
