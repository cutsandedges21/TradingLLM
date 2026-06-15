# Trading LLM v2 — Redesign Roadmap

**Vision:** a local, paper-only, **educational quant-research workstation** — Vibe-Trading-level
capability, TradingAgents-style multi-agent reasoning, freqtrade/nautilus-grade backtesting,
wrapped in a "teach the user trading" layer. Strategy: **redesign our codebase with heavy reuse**
of the 5 cloned repos (see [REPO_INVENTORY.md](REPO_INVENTORY.md)).

"Educational" means **the app teaches the user about trading** (explain indicators, justify each
trade, surface the relevant skill pack, beginner mode, practice challenges). It is *not* a
constraint on code simplicity.

## Principles
- **Local & private** by default; **paper/simulated only** — no real money. Any future broker
  path stays dormant behind a mandate / kill-switch safety model.
- **Free data first** (Finnhub/yfinance + crypto), automatic fallback.
- **Web only** interface (React UI over FastAPI). Tkinter retired.
- Every capability is **wrapped to teach**: the "why" (debate transcript, indicator, skill pack)
  is always available; a beginner-mode toggle controls depth.

## Phases (each = its own spec → plan → build cycle)
| Phase | Theme | Pulls from |
|------|-------|-----------|
| **0** | **Foundation** — v2 package, config, provider seam, memory, parity. ✅ done | — |
| **1** | **Reasoning brain** — multi-agent debate + reflection-learning. ✅ done | TradingAgents |
| **2** | **Backtesting** — engine, strategies, metrics, NL→backtest + explainer. ✅ done | Vibe-Trading, freqtrade |
| **3** | **Quant/factors** — factor zoo (classic + alpha101) + IC/IR bench, explained. ✅ done | Vibe-Trading |
| **4** | **Teaching layer** — finance skill packs + explain/cite + beginner mode. ✅ done | Vibe-Trading |
| **5** | **Shadow account + gamification** — journal diagnostics, scorecard, challenges. ✅ done | Vibe-Trading, AI-Trader |
| **6** | **UI Studio** — dedicated views: backtest + equity chart, factor table, coach panel. ✅ done | — |
| **7** | **Engine realism + strategy tooling** — fill slippage/fees + hyperparameter optimization. ✅ done | freqtrade, nautilus |

**🎉 Core roadmap complete — Phases 0–7 all shipped and verified.**

## Extension roadmap (post-core)
| Phase | Theme | Pulls from |
|------|-------|-----------|
| **8** | **Agent-native** — tool registry + LLM tool-calling loop + **MCP server** (expose the app's tools to Claude Desktop / any agent). ✅ done | Vibe-Trading |
| **9** | **Strategy generation & export** — NL → safe rule DSL → compiled backtest; export to TradingView **Pine Script v6**. ✅ done | Vibe-Trading |
| **10** | **Streaming & research memory** — live SSE committee progress + persistent notes memory + research goals. ✅ done | Vibe-Trading |
| **11** | **Opt-in broker + final QA** — Alpaca paper trading behind a mandate / kill-switch / audit safety model; README refresh + accessibility. ✅ done | Vibe-Trading, AI-Trader |

**🎉 Entire roadmap complete — Phases 0–11 all shipped and verified (145 passing tests).**
Run the MCP server with `python -m trading_llm.agentic.mcp_server`.

## Deliberately out of scope
Social/copy-trading platform & hosted leaderboards (AI-Trader), prediction markets, real-money
live trading, nautilus Rust engine port (kept as an optional future upgrade only).
