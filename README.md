# Trading LLM v2

A **local, private, educational quant-research workstation** that lives on your laptop. It reads
**live** market data (free — no brokerage signup), reasons over it with a **multi-agent LLM
committee**, **backtests** strategies, scores a **factor zoo**, profiles **your own trading**,
teaches you as it goes — and lets you place **simulated** trades against a built-in **$100k mock
account**. Everything is remembered in local files.

> Simulated money by default. Not financial advice. See `LEARN_TO_TRADE.md`.
> This is a redesign that pulls the best ideas from five open-source trading projects into one
> teachable app — see [`docs/REDESIGN_ROADMAP.md`](docs/REDESIGN_ROADMAP.md) (Phases 0–11).

---

## Quick start

```bash
pip install -r requirements.txt        # core deps; optional extras enable advanced features
python app_web.py                      # opens http://127.0.0.1:8000 in your browser
```
…or double-click **`Run Trading LLM (Web).bat`**. The web UI is the single interface. Your
Gemini/OpenRouter/Finnhub keys are pre-filled, and the $100k paper account is created
automatically. Stocks and crypto are live immediately, no signup.

> Edited the UI in `web/`? Rebuild it: `cd web && npm install && npm run build`.

---

## What it can do

Just chat in the **Terminal**, or use the **Studio** tabs. Things to try:

| Ask / do | What happens |
|---|---|
| “How does NVDA look today?” | Live snapshot + reasoning, citing relevant **knowledge topics** |
| Toggle **🔬 Deep**, “deep analysis of NVDA” | A **multi-agent committee** (technical · news · **smart-money & regime** analysts → bull/bear debate → trader → risk debate → portfolio manager) streams its progress live and returns a Research Brief + rating, and **learns from past calls** |
| “Backtest a 20/50 SMA crossover on AAPL” | Runs a real backtest → metrics + **equity-curve chart** vs buy & hold + plain-English verdict |
| “Optimize the SMA crossover on AAPL” | Sweeps parameters (hyperopt) and shows the best — with an overfitting caveat |
| “Which alpha factors work right now?” | Scores a **factor zoo** (classic + Kakushadze alpha101) by **IC/IR** over a live universe |
| “Build a strategy that buys RSI dips above the 200-day average” | Generates a rule strategy, backtests it, and exports **TradingView Pine Script** |
| “What are insiders / big funds doing in NVDA?” | The **Smart Money** view: corporate **insider trades** (SEC Form 4), **institutional 13F** holdings of tracked funds (Berkshire, Citadel…), and congressional trades — surfaced honestly with each filing's date + lag |
| Check the **regime chip** (top bar) | A live **market-regime** read — risk-on/neutral/risk-off from trend, breadth, volatility & momentum — that frames every signal |
| “Does insider buying actually work for NVDA?” | An **event study**: forward 30/60/90-day return after every past occurrence, **alpha vs SPY**, the signal's **edge** over the stock's normal drift, a **t-stat**, and an **out-of-sample** check — so you see whether a signal is real or just noise |
| **Scan for ideas** (Smart Money) | Surfaces fresh **insider-buying clusters** as small, paper-only **trade ideas** you confirm — then a **track record** records each call's realized **alpha vs SPY** at 60 days and builds **base rates** by regime, so the app learns what actually works for you |
| Confirm any trade | A **pre-trade risk check** runs first — position size vs caps, concentration, portfolio heat, buying power, stop defined, daily budget — shown right in the confirm dialog |
| **Studio → Risk** | A risk engine: **position-size calculator** (risk a fixed % per trade, auto 2·ATR stops), **Kelly** sizing from your own win rate/payoff, **risk-of-ruin** curves, and live **portfolio heat** |
| **Load edge signals** (Smart Money) | Four under-crowded, free signals per symbol: **options flow** (put/call, IV, unusual volume), **short-interest squeeze** score, **post-earnings drift** (PEAD), and **seasonality** (month/day-of-week/turn-of-month) |
| **Run scanner** (Smart Money) | A **composite scanner** ranks the universe by a transparent blend of momentum + insider + 13F + seasonality + squeeze, **regime-gated** — click any row to see exactly which signals drove the score |
| **Studio → Alerts** | Define **rules** (AND-conditions over any signal) that fire **alerts with pre-sized proposals** when they hit; **walk-forward backtest** the price-based conditions (smart-money ones are forward-only by design) |
| “How am I doing?” / “Review my trades” | A discipline **scorecard + challenges**, and a **behavior review** (disposition effect, overtrading…) |
| “Remember I prefer swing trades” / “Set a goal to decide on NVDA” | Persistent **notes** + **research goals** that carry across sessions |
| Toggle **Beginner mode** | The copilot defines every term and explains everything simply |

**Studio** (left rail): **Backtest** (chart + optimize) · **Builder** (NL → strategy → Pine) ·
**Factor Zoo** (IC/IR table) · **Coach** (scorecard, challenges, shadow review).
**Library**: 14 finance knowledge packs the copilot cites.

---

## Where the data comes from (all free)

| Data | Source | Key needed? |
|---|---|---|
| Real-time **stock** quotes | Finnhub | included |
| **Stock + crypto** history (charts, indicators, backtests) | yfinance (Yahoo) | none |
| **Crypto** prices + sub-minute candles | Binance (+ Alpaca crypto fallback) | none |
| Market **news** | Finnhub | included |
| **Insider trades** (Form 4) + **institutional 13F** holdings | SEC EDGAR (official) | none (needs a real `User-Agent`) |
| **Congressional trades** | free public source (often gated) | none — degrades to "unavailable" |
| Market **regime** (trend/breadth/vol/momentum) | computed **locally** from SPY + universe bars | — |
| RSI / SMA / EMA / MACD | computed **locally** | — |
| Reasoning | Gemini → OpenRouter → local Ollama (fallback) | included |

The LLM never supplies prices — it reasons over the live snapshot. Sources fall back automatically.
Smart-money signals are **public, lagged** disclosures (Form 4 ~2 days, 13F ~45 days) — surfaced as
*information/context*, never as buy/sell instructions, and never a guaranteed edge.

---

## Trading: mock by default, real paper optional

- **Default:** a local **mock broker** (`broker/paper_broker.py`) — $100k fake cash, fills at the
  live price (with an optional fee/slippage model), tracks positions and P/L on disk. The LLM
  *proposes*; a confirm dialog appears before anything is recorded.
- **Opt-in real (Alpaca PAPER):** add Alpaca paper keys and commit a **mandate** (per-order cap,
  daily cap, symbol allow-list). Every order then passes a **safety guard** — a filesystem
  **kill-switch** halts instantly, and all attempts are written to an **audit log**. Off by
  default; see `broker/safety.py`.

---

## Security & secrets

This is a **local, single-user** app — it binds to `127.0.0.1` and trusts loopback.

- **Remote access requires a key.** Any non-loopback request to `/api/*` must send
  `X-API-Key: <key>` where the key is set via `TRADING_LLM_API_KEY` (env) or `api_auth_key`
  (settings). Without a key configured, non-local requests are refused outright. Local use is
  unaffected.
- **Keep secrets out of the synced folder.** This project lives in OneDrive, so `api_keys.json`
  is cloud-synced. Prefer **environment variables** — they override the file:
  `GEMINI_API_KEYS`, `OPENROUTER_API_KEYS`, `FINNHUB_API_KEY`, `ALPACA_PAPER_KEY`,
  `ALPACA_PAPER_SECRET`. `api_keys.json` and all of `memory/*` are `.gitignore`d.
- **Memory writes are atomic** (temp-file + replace), so a crash or sync mid-write won't corrupt
  your journal/account files.

## Use it from other agents (MCP)

Expose the app's tools (quotes, backtest, optimize, factor scan, trade review, scorecard, notes,
goals) to Claude Desktop / Cursor / any MCP client:

```bash
python -m trading_llm.agentic.mcp_server      # stdio MCP server
```

---

## Optional features & their extras

The core runs on the base requirements. These unlock more (in `requirements.txt`):
- **Multi-agent debate / strategy generation** → `langchain-google-genai` (Gemini tool-calling)
- **Agent tools over MCP** → `mcp`
- **Real paper trading** → `alpaca-py`
- **Offline brain** → `ollama` (`ollama serve` + `ollama pull llama3.1:8b`)

Without an extra, the related feature degrades gracefully (e.g. deep analysis falls back to a
single-brain reply) — the rest of the app keeps working.

---

## Verify it works (offline, no keys/network)

```bash
python tests/smoke_test.py
```
263 deterministic checks across indicators, memory, the mock broker, backtesting + out-of-sample
optimization, the factor zoo, the strategy DSL + Pine export, the agent tools, the safety guard,
API auth, atomic writes, the **market-regime detector**, **smart-money signal parsing**
(SEC Form 4 / 13F / congress), the **signal event-study** (edge, t-stat, in/out-of-sample), the
**smart-money committee analyst**, the **signal learning loop** (record → resolve → base rates),
the **risk & position-sizing engine** (Kelly, risk-of-ruin, portfolio heat, pre-trade checklist),
the **under-crowded edge signals** (options flow, short-interest squeeze, PEAD, seasonality), the
**composite scanner** (transparent weighted blend that reconstructs to its score), and the
**automation/alerts engine** (rule evaluation + honest walk-forward backtest) —
all from saved fixtures + synthetic series, no network.

---

## Configure → `config/settings.json`
- `watchlist`, `data_source_order`, `default_timeframe`, `mock_starting_cash`
- `llm.*` — models + provider order (deep model is `gemini-2.5-flash`; pro has no free quota)
- `risk.*` — paper-trade guardrails · `execution.*` — fee/slippage realism
- `debate.*` — committee depth · `beginner_mode` · `live_trading.*` — the real-broker mandate
- `signals.*` — smart-money/regime: `sec_user_agent` (**required by SEC**), `famous_filers` (13F
  CIKs to track), `cache_ttl_hours`, per-source toggles, optional `congress_sources`

## Where your memory lives (never leaves your machine)
`memory/`: `profile.json`, `journal.json`, `decision_log.json`, `notes.json`, `goals.json`,
`paper_account.json`. Delete to start fresh; back up to keep your history.

---

## Project layout
All app code is in the `trading_llm/` package:
```
app_web.py                 launcher → trading_llm.server:app
trading_llm/
  core/      paths · config · engine (the orchestrator)
  brain/     providers (router + LangChain seam) · prompts · clients/
             debate/ (multi-agent committee) · reflection/ (learn from outcomes)
  agentic/   tools · loop (tool-calling) · mcp_server
  market/    data · indicators · snapshot · alpaca_client
  backtest/  engine · strategies · metrics · hyperopt · dsl · pine · custom
  factors/   operators · library (alpha zoo) · scoring (IC/IR) · runner
  signals/   regime · edgar (Form 4 + 13F) · congress · eventstudy · learning · service · format
  risk/      sizing (fixed-fractional · Kelly · risk-of-ruin · portfolio heat · pre-trade check)
  edge/      seasonality · short_interest · options_flow · pead (under-crowded signals)
  scanner/   composite (transparent weighted blend → ranked universe)
  alerts/    rules · store · walkforward (rule automation + honest backtest)
  broker/    paper_broker · safety (mandate/kill-switch/audit)
  memory/    profile · journal · decision_log · notes · goals · store
  learn/     skills/ (knowledge packs) · guide
  shadow/    trades · diagnostics · report      gamify/ scorecard · challenges
  server.py  FastAPI API
web/                       React + Tailwind UI    docs/  roadmap + specs
LEARN_TO_TRADE.md          from-zero beginner guide
```
