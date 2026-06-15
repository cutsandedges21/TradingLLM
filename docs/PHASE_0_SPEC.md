# Phase 0 — Foundation (spec)

Part of the **Trading LLM v2** redesign (see [REDESIGN_ROADMAP.md](REDESIGN_ROADMAP.md) and
[REPO_INVENTORY.md](REPO_INVENTORY.md)). Phase 0 stands up the v2 architecture and reaches
**feature parity with the current app on the new structure**. No new user-facing capability.

## Outcome
A new `trading_llm/` package becomes the app's home. The current single-Brain chat flow,
live data, mock broker, and JSON memory all run through the new layout. Entry points switch
to the package; the old top-level modules and the Tkinter desktop UI are removed.

## Target layout (Phase 0 builds the seams; later phases fill the stubs)
```
trading_llm/
  core/      paths.py · config.py · engine.py        (config/memory/web roots stay at repo root)
  brain/     providers.py (router) · clients/ (gemini/openrouter/ollama) · prompts.py
             debate/  __init__.py  ← Phase 1 stub
             reflection/ __init__.py ← Phase 1 stub
  agentic/   __init__.py            ← Phase 1/2 stub (tool loop)
  market/    data.py · indicators.py · snapshot.py · alpaca_client.py · loaders/ (stub)
  broker/    paper_broker.py
  memory/    profile.py · journal.py · store.py · decision_log.py (Phase-1-ready scaffold)
  backtest/  __init__.py            ← Phase 2 stub
  factors/   __init__.py            ← Phase 3 stub
  learn/     guide.py · skills/ (stub) · challenges/ (stub) ← Phase 4/5
  shadow/    __init__.py            ← Phase 5 stub
  server.py  FastAPI app (same endpoints)
app_web.py   thin launcher at repo root → trading_llm.server:app
```

Data/asset roots are unchanged and stay at the repo root: `config/`, `memory/*.json`,
`web/dist/`, `LEARN_TO_TRADE.md`. `core/paths.py` computes `BASE_DIR` = repo root.

## Key decisions
- **Web only.** Remove `app.py`, `ui/`, desktop launcher. Keep the React `web/` UI served as-is.
- **Provider layer = hybrid seam.** `brain/providers.py` keeps the proven Gemini (multi-key
  rotation) / OpenRouter (multi-model rotation) / Ollama clients for the `chat()` path — this
  preserves exact current behavior, free-tier rotation, and offline-safety. It **adds**
  `get_llm(kind="deep"|"quick")` returning a **LangChain** chat model — the seam TradingAgents
  / Vibe need in Phase 1. LangChain is an **optional** dependency: importing the package and
  running offline tests must not require it; `get_llm` raises a clear "install langchain-…"
  message if unavailable. (Rationale: rebuilding the free-tier key/model rotation on LangChain
  now would risk parity with no Phase-0 benefit; the seam is what Phase 1 actually needs.)
- **Memory preserved.** `profile.json` / `journal.json` / `paper_account.json` formats and data
  are untouched; `store.py` centralizes paths; `decision_log.py` is a new, functional but small
  JSON log that Phase 1's reflection loop will build on.
- **Python ≥ 3.11.**

## Non-goals (Phase 0)
No multi-agent debate, backtesting, factors, skills, shadow account, challenges, or web-UI
redesign. Reasoning quality must match today's.

## Acceptance criteria
1. `python tests/smoke_test.py` passes **offline** (indicators, memory profile+journal,
   mock broker incl. shorts, data helpers, trade parsing, provider router import, decision log).
2. `python -c "import trading_llm.server"` imports cleanly (no langchain required).
3. `python app_web.py` boots the FastAPI server and serves the existing UI; chat → reply
   (single-Brain via router), watchlist + account load, propose → confirm → record a paper
   trade — **full parity with today**.
4. Existing `memory/*.json` read intact; Tkinter fully removed; no dangling imports.
