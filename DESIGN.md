# Trading LLM — Design

A local, memory-keeping market assistant that reads **live** market data, helps you
analyze and learn, and lets you place **simulated** trades against a built-in mock
account — no brokerage signup required.

## Decisions
- **Brain:** Hybrid, smart-first. Gemini (rotating 2 keys) → OpenRouter (2 keys) →
  local Ollama (offline fallback). The model is interchangeable; your data is local.
- **Data (free, no signup):** Finnhub (real-time stock quotes + news) + yfinance
  (stock/crypto bars + crypto prices), with Alpaca crypto as a fallback. Sources fall
  back automatically; order is set in `settings.json` → `data_source_order`.
- **Scope:** Advisor **+ paper trading** via a built-in local **mock account** ($100k).
  It proposes, you confirm, then the simulated order is recorded on disk. Real Alpaca
  paper trading is an optional drop-in if keys are added.
- **Interface:** Local **web UI** (React + Tailwind) over a small local FastAPI server.
  This is the single interface — the original Tkinter desktop window was retired in the
  v2 redesign (see `docs/REDESIGN_ROADMAP.md`).

## The "Alpaca" clarification
`alpaca-py` is the **Alpaca Markets** API (data + brokerage), unrelated to LLM training
("Stanford Alpaca" is a different thing). We don't train a model on the market — markets
change constantly. Instead we use **RAG + memory**: pull live data into context at
question-time and persist everything locally. (We later moved primary data to
Finnhub/yfinance because Alpaca requires identity verification; Alpaca remains an
optional crypto/trading source.)

## Architecture (v2)
All code lives in the `trading_llm/` package. Phase 0 ports the original single-Brain
app onto this structure at parity; later phases fill the stubs (see
`docs/REDESIGN_ROADMAP.md`).
```
app_web.py             thin launcher -> starts FastAPI + opens browser
trading_llm/
  server.py            FastAPI API wrapping the engine + serving web/dist
  core/  paths.py      repo-root paths + JSON helpers
         config.py     settings/keys loading with defaults
         engine.py     assemble context -> brain -> parse trade -> risk gate -> mock order
                       (multi-agent debate plugs into the _reason() seam in Phase 1)
  brain/ providers.py  router: chat() with provider fallback + get_llm() LangChain seam
         clients/      gemini / openrouter / ollama transports (multi-key/model rotation)
         prompts.py    system persona + trade-proposal contract + memory extraction
         debate/ reflection/   Phase 1 stubs (TradingAgents)
  market/ data.py      MarketData: Finnhub/yfinance/Alpaca/Binance, fallback + TTL cache
          indicators.py SMA/EMA/RSI/MACD (local, pandas)
          snapshot.py   live "current market" context + UI rows
          alpaca_client.py optional Alpaca data/trading (crypto keyless)
  broker/ paper_broker.py local mock account (cash/positions/P&L on disk)
  memory/ profile.py · journal.py · decision_log.py · store.py
  agentic/ backtest/ factors/ learn/ shadow/   later-phase stubs
memory/  profile.json · journal.json · paper_account.json   (data, never auto-deleted)
LEARN_TO_TRADE.md      full beginner guide (also rendered in the Learn tab)
```

## Data flow for one question
1. Detect tickers in the message; always include the watchlist.
2. Build context: live snapshot (prices, RSI/SMA/MACD, news) + mock account + positions
   + trader profile + recent journal + current date/time.
3. Send to the Brain (Gemini first); fall back automatically if needed.
4. Show the reply. If it contains a ```trade block, parse it.
5. Risk gates (max position $, max trades/day) → confirmation dialog → mock order.
6. Persist: journal the exchange/trade; background-extract durable profile facts.

## Memory = real persistence
Local JSON, never auto-deleted: `memory/profile.json` (risk, style, lessons),
`memory/journal.json` (every observation + trade), `memory/paper_account.json` (mock
cash + positions). This is how it "learns over time" — it accumulates and re-reads
its own history.

## Safety
- Simulated money by default (`trading_mode: mock`; built-in account).
- The model can never place an order silently — explicit user confirmation required.
- Position-size and daily-trade limits in `config/settings.json`.

## Education requirement
A complete from-zero **Learn to Trade** guide (`LEARN_TO_TRADE.md`) ships with the app
and is readable in-app, so a total beginner can understand trading and place a first
simulated trade confidently.

## Deliberate non-goals (v1, YAGNI)
- No vector database (structured JSON + live snapshot is enough).
- No provider-specific function-calling (trades are provider-agnostic JSON blocks).
- No real-money trading.
