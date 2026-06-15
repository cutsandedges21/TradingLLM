"""Offline smoke tests — no API keys, no network.

Run:  python tests/smoke_test.py
Covers deterministic logic in the v2 ``trading_llm`` package: indicators,
persistent profile + journal, the decision log, the local mock paper broker,
data helpers, trade-proposal parsing, the provider router, and (when the lib is
present) the Gemini content builder. On-disk state is redirected to a temp dir.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = ""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}  {detail}")


def test_indicators():
    print("[indicators]")
    from trading_llm.market import indicators
    rising = list(range(10, 80))
    ind = indicators.compute(rising)
    check("price is last close", ind["price"] == 79.0, str(ind["price"]))
    check("trend up", ind["trend"] == "up", str(ind["trend"]))
    check("rsi high on uptrend", (ind["rsi"] or 0) > 60, str(ind["rsi"]))
    check("sma20 > sma50 on uptrend", (ind["sma20"] or 0) > (ind["sma50"] or 0),
          f"{ind['sma20']} vs {ind['sma50']}")
    check("momentum bullish", ind["momentum"] == "bullish", str(ind["momentum"]))
    check("empty -> price None", indicators.compute([])["price"] is None)


def test_memory(tmp: Path):
    print("[memory: profile + journal]")
    from trading_llm.memory import profile as profile_mem
    from trading_llm.memory import journal
    profile_mem.PROFILE_PATH = tmp / "profile.json"
    journal.JOURNAL_PATH = tmp / "journal.json"

    profile_mem.update_profile({"risk_profile": {"max_position": {"value": "$500 per trade"}}})
    check("profile persisted",
          profile_mem.load_profile()["risk_profile"]["max_position"]["value"] == "$500 per trade")
    journal.add_entry("trade", symbol="AAPL", side="buy", qty=2, price=190.0, status="filled")
    check("journal records trade", journal.trades_today() == 1, str(journal.trades_today()))
    check("journal formats", "AAPL" in journal.format_for_prompt(10))


def test_decision_log(tmp: Path):
    print("[memory: decision log]")
    from trading_llm.memory import decision_log
    decision_log.LOG_PATH = tmp / "decision_log.json"

    decision_log.store_decision("NVDA", "2026-01-15", "FINAL: BUY — momentum + earnings beat.")
    check("decision stored as pending", len(decision_log.get_pending_entries()) == 1)
    n = decision_log.batch_update_with_outcomes([{
        "ticker": "NVDA", "trade_date": "2026-01-15",
        "raw_return": 0.05, "alpha_return": 0.02, "holding_days": 5,
        "reflection": "Directional call correct; thesis held.",
    }])
    check("outcome attached to 1 entry", n == 1, str(n))
    check("no pending after reflect", len(decision_log.get_pending_entries()) == 0)
    ctx = decision_log.get_past_context("NVDA")
    check("past context cites ticker + lesson",
          "NVDA" in ctx and "thesis held" in ctx, ctx)


def test_paper_broker(tmp: Path):
    print("[paper broker]")
    from trading_llm.broker import paper_broker
    paper_broker.ACCOUNT_PATH = tmp / "paper_account.json"
    b = paper_broker.PaperBroker(starting_cash=10000)
    prices = {"AAPL": 100.0, "BTC/USD": 50000.0}
    pf = lambda s: prices.get(s)

    r = b.place_order("AAPL", "buy", qty=10, price_fn=pf)
    check("buy fills at price", r.get("status") == "filled" and r["filled_avg_price"] == 100.0, str(r))
    acct = b.get_account(pf)
    check("cash reduced by cost", abs(acct["cash"] - 9000.0) < 1e-6, str(acct["cash"]))
    check("equity marks to market", abs(acct["equity"] - 10000.0) < 1e-6, str(acct["equity"]))

    prices["AAPL"] = 110.0
    pos = b.get_positions(pf)
    check("unrealized P/L tracks price", abs(pos[0]["unrealized_pl"] - 100.0) < 1e-6, str(pos))

    r2 = b.place_order("BTC/USD", "buy", notional=5000, price_fn=pf)
    check("notional buy -> fractional qty", abs(r2["qty"] - 0.1) < 1e-9, str(r2))
    check("insufficient cash blocked", "error" in b.place_order("AAPL", "buy", qty=100, price_fn=pf))

    # short selling: sell with no/short position -> go short, profit when price falls
    prices["MSFT"] = 200.0
    b.place_order("MSFT", "sell", qty=5, price_fn=pf)
    short = next(p for p in b.get_positions(pf) if p["symbol"] == "MSFT")
    check("short opens negative position", short["qty"] == -5 and short["side"] == "short", str(short))
    prices["MSFT"] = 190.0
    short = next(p for p in b.get_positions(pf) if p["symbol"] == "MSFT")
    check("short profits when price falls", abs(short["unrealized_pl"] - 50.0) < 1e-6, str(short))
    b.place_order("MSFT", "buy", qty=5, price_fn=pf)  # cover
    check("cover closes short", not any(p["symbol"] == "MSFT" for p in b.get_positions(pf)))


def test_data_helpers():
    print("[data helpers]")
    from trading_llm.market.data import is_crypto, to_yf
    check("is_crypto slash", is_crypto("BTC/USD"))
    check("is_crypto dash", is_crypto("ETH-USD"))
    check("stock not crypto", not is_crypto("AAPL"))
    check("to_yf converts slash", to_yf("BTC/USD") == "BTC-USD")
    check("to_yf leaves stock", to_yf("AAPL") == "AAPL")


def test_trade_parsing(tmp: Path):
    print("[engine: trade parsing + symbol detection]")
    from trading_llm.broker import paper_broker
    paper_broker.ACCOUNT_PATH = tmp / "engine_paper.json"
    from trading_llm.core.engine import TradingEngine
    eng = TradingEngine()

    buy = ('Idea:\n```trade\n{"action":"buy","symbol":"AAPL","qty":2,'
           '"order_type":"market","rationale":"momentum"}\n```')
    p = eng._parse_trade(buy)
    check("parses buy block", p and p["action"] == "buy" and p["symbol"] == "AAPL" and p["qty"] == 2, str(p))

    p2 = eng._parse_trade('```trade\n{"action":"sell","symbol":"btc","notional":250}\n```')
    check("crypto alias + notional", p2 and p2["symbol"] == "BTC/USD" and p2["notional"] == 250, str(p2))

    check("no block -> None", eng._parse_trade("Just an explanation.") is None)
    syms = eng._symbols_for("What about $AMD and NVDA today?")
    check("detects $AMD + keeps watchlist", "AMD" in syms and "NVDA" in syms, str(syms))
    check("stopword not a ticker", "RSI" not in eng._symbols_for("explain RSI please"))


def test_provider_router():
    print("[brain: provider router]")
    from trading_llm.brain.providers import ProviderRouter
    settings = {"llm": {"provider_order": ["gemini", "openrouter", "ollama"],
                        "gemini_model": "gemini-2.5-flash", "gemini_deep_model": "gemini-2.5-pro",
                        "openrouter_models": [], "ollama_model": "llama3.1:8b",
                        "temperature": 0.4, "max_tokens": 2048}}
    r = ProviderRouter(settings, {"gemini_api_keys": [], "openrouter_api_keys": []})
    status = r.providers_status()
    check("status has all providers", set(status) == {"gemini", "openrouter", "ollama"}, str(status))
    check("no keys -> gemini unavailable", r.gemini.available is False)
    check("chat_json returns {} offline", r.chat_json("sys", "prompt") == {})
    raised = False
    try:
        r.chat("sys", [{"role": "user", "content": "hi"}])
    except RuntimeError:
        raised = True
    check("chat raises with no provider", raised)
    # get_llm seam exists and is callable (may raise a clear install/no-provider error)
    check("get_llm seam present", callable(getattr(r, "get_llm", None)))


def test_gemini_contents():
    print("[gemini: content builder]")
    from trading_llm.brain.clients import gemini_client
    if not gemini_client._GENAI_OK:
        check("google-genai absent -> skipped", True, "(optional lib not installed)")
        return
    g = gemini_client.GeminiClient([], "gemini-2.5-flash", "gemini-2.5-pro")
    contents = g._to_contents([{"role": "user", "content": "hi"},
                               {"role": "assistant", "content": "hello"}])
    check("builds 2 contents", len(contents) == 2)
    check("maps assistant->model", contents[1].role == "model", contents[1].role)
    check("unavailable with no keys", g.available is False)


# ---- fakes for the multi-agent debate (no network, no LLM) ----
class _FakeMsg:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, text="Rating: Buy\nConstructive on momentum; stop below support."):
        self.text = text
        self.calls = 0
        self.prompts = []

    def invoke(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        return _FakeMsg(self.text)


class FakeRouter:
    def __init__(self, llm=None, raises=False):
        self._llm = llm or FakeLLM()
        self.raises = raises

    def get_llm(self, kind="quick", provider=None):
        if self.raises:
            raise RuntimeError("langchain not installed")
        return self._llm


def test_signal():
    print("[debate: rating + proposal]")
    from trading_llm.brain.debate.signal import parse_rating, rating_to_proposal
    check("label parse (bold)", parse_rating("x\nRating: **Sell**\ny") == "Sell")
    check("word fallback parse", parse_rating("I lean Overweight here") == "Overweight")
    check("default Hold", parse_rating("no rating word at all") == "Hold")
    p = rating_to_proposal("Buy", "NVDA", 2000)
    check("Buy -> buy proposal", p and p["action"] == "buy" and p["symbol"] == "NVDA"
          and p["notional"] == 2000.0, str(p))
    check("Hold -> no proposal", rating_to_proposal("Hold", "NVDA", 2000) is None)
    check("Underweight -> sell", rating_to_proposal("Underweight", "NVDA", 2000)["action"] == "sell")


def test_debate_pipeline():
    print("[debate: pipeline with fake LLM]")
    from trading_llm.brain.debate import DebateEngine
    fake = FakeLLM("Rating: Buy\nThe committee is constructive on NVDA's momentum.")
    eng = DebateEngine(FakeRouter(fake), {"debate": {"research_rounds": 1, "risk_rounds": 1}})
    check("engine available with provider", eng.available() is True)
    res = eng.run("NVDA", "RSI 55, trend up, SMA20 > SMA50", "- A bullish headline")
    check("rating parsed from PM", res.rating == "Buy", res.rating)
    check("all stages populated",
          all([res.market_report, res.news_report, res.research_debate,
               res.investment_plan, res.trader_plan, res.risk_debate, res.final_decision]))
    check("10 LLM calls (1+1 rounds)", fake.calls == 10, str(fake.calls))
    md = res.to_markdown()
    check("transcript markdown has ticker + sections",
          "NVDA" in md and "Technical analyst" in md and "Risk committee" in md)


def test_debate_unavailable():
    print("[debate: graceful unavailable]")
    from trading_llm.brain.debate import DebateEngine
    eng = DebateEngine(FakeRouter(raises=True), {})
    check("unavailable when get_llm raises", eng.available() is False)


def test_reflection(tmp: Path):
    print("[reflection: resolve pending decisions]")
    from trading_llm.memory import decision_log
    from trading_llm.brain import reflection
    decision_log.LOG_PATH = tmp / "reflect_log.json"
    decision_log.store_decision("AAPL", "2026-01-01", "FINAL: Buy on strong momentum.")

    orig = reflection.fetch_returns
    reflection.fetch_returns = lambda t, d, holding_days=5, benchmark=None: (0.04, 0.012, 5)
    try:
        n = reflection.resolve_pending(FakeRouter(FakeLLM("Call worked; momentum thesis held.")), "AAPL")
    finally:
        reflection.fetch_returns = orig
    check("reflected 1 entry", n == 1, str(n))
    check("no pending after reflect", len(decision_log.get_pending_entries()) == 0)
    ctx = decision_log.get_past_context("AAPL")
    check("lesson available in past context", "momentum thesis held" in ctx, ctx)


def _synth_df(prices):
    import pandas as pd
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    p = [float(x) for x in prices]
    return pd.DataFrame({"open": p, "high": p, "low": p, "close": p,
                         "volume": [1000] * len(p)}, index=idx)


def test_backtest():
    print("[backtest: strategies + engine + metrics + runner + explain]")
    from trading_llm.backtest import strategies, explain
    from trading_llm.backtest import engine as bteng
    from trading_llm.backtest import metrics as btm
    from trading_llm.backtest import data as btdata
    from trading_llm.backtest import runner

    df = _synth_df(range(100, 200))  # strictly rising

    bh = strategies.get_strategy("buy_hold").signal(df)
    check("buy_hold is always long", float(bh.sum()) == len(df))
    sc = strategies.get_strategy("sma_cross").signal(df, {"fast": 5, "slow": 20})
    check("sma_cross long at uptrend end", float(sc.iloc[-1]) == 1.0)

    run = bteng.run(df, bh, initial=10000, cost_bps=5)
    check("buy_hold equity rises on uptrend", run.equity.iloc[-1] > run.equity.iloc[0])
    m = btm.compute(run)
    check("positive total return", m["total_return_pct"] > 0, str(m["total_return_pct"]))
    check("full exposure ~100%", m["exposure_pct"] >= 99, str(m["exposure_pct"]))
    check("metrics include sharpe + drawdown", "sharpe" in m and "max_drawdown_pct" in m)

    # runner with data monkeypatched (no network)
    orig = btdata.load_ohlc
    btdata.load_ohlc = lambda symbol, period="2y", interval="1d": df
    try:
        res = runner.backtest("AAPL", "sma_cross", {"fast": 5, "slow": 20})
    finally:
        btdata.load_ohlc = orig
    check("runner ok with data", res.ok, res.error)
    check("runner produced metrics + curve", bool(res.metrics) and len(res.equity_curve) > 0)
    md = explain(res)
    check("explainer renders markdown brief", "Backtest" in md and "Buy & Hold" in md)
    check("unknown strategy -> not ok", runner.backtest("AAPL", "nonsense").ok is False)


class FakeEngine:
    """Minimal engine stand-in for tool-registry tests (no network/LLM)."""
    def account(self): return {"equity": 100000.0, "cash": 100000.0, "status": "MOCK"}
    def positions(self): return []
    def quotes(self, syms): return [{"symbol": s, "price": 100.0, "change_pct": 0.5} for s in syms]
    def watchlist_rows(self): return []
    def list_skills(self): return [{"name": "rsi", "title": "RSI"}]
    def get_skill(self, n): return {"name": n, "title": n}
    def backtest_spec(self, s): return {"explanation": "backtest result"}
    def optimize_spec(self, s): return {"explanation": "optimize result"}
    def factor_bench(self, s): return {"explanation": "factor result"}
    def shadow_review(self): return {"reply": "review"}
    def coach(self): return {"reply": "coach"}


def test_agentic():
    print("[agentic: tool registry + loop + MCP]")
    import json as _json
    from trading_llm.agentic import build_registry, AgentLoop
    reg = build_registry(FakeEngine())
    check("registry has >= 10 tools", len(reg) >= 10, str(len(reg)))
    check("openai schemas well-formed", all("function" in s for s in reg.openai_schemas()))
    acct = _json.loads(reg.execute("account_summary", {}))
    check("account_summary tool executes", acct["account"]["equity"] == 100000.0)
    quote = _json.loads(reg.execute("get_quote", {"symbol": "aapl"}))
    check("get_quote uppercases + runs", quote[0]["symbol"] == "AAPL")
    check("unknown tool -> error json", "error" in reg.execute("nope", {}))

    # tool-calling loop with a scripted fake LLM
    class FakeResp:
        def __init__(self, content="", tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []

    class FakeLLM2:
        def __init__(self, script): self.script = script; self.i = 0
        def bind_tools(self, schemas): return self
        def invoke(self, messages):
            r = self.script[min(self.i, len(self.script) - 1)]; self.i += 1; return r

    class FakeRouter2:
        def __init__(self, llm): self._llm = llm
        def get_llm(self, kind="quick", provider=None): return self._llm

    script = [FakeResp(tool_calls=[{"name": "account_summary", "args": {}, "id": "1"}]),
              FakeResp(content="You have $100,000 in cash and no open positions.")]
    loop = AgentLoop(FakeRouter2(FakeLLM2(script)), reg)
    check("agent loop available", loop.available() is True)
    out = loop.run("how much cash do I have?", "system")
    check("loop calls tool then answers", "100,000" in out["reply"], out["reply"])
    check("loop reports tool used", out["tools_used"] == ["account_summary"], str(out["tools_used"]))

    from trading_llm.agentic import mcp_server
    srv = mcp_server.build_server()
    try:
        import asyncio
        tools = asyncio.run(srv.list_tools())
        check("MCP server exposes >= 10 tools", len(tools) >= 10, str(len(tools)))
    except Exception:
        check("MCP server builds", srv is not None)


def test_hardening(tmp: Path):
    print("[hardening: atomic writes, env keys, auth, fallback, routing]")
    import os
    from trading_llm.core import paths, config

    p = tmp / "atomic.json"
    paths.save_json(p, {"a": 1, "b": [2, 3]})
    check("atomic write round-trips", paths.load_json(p, None) == {"a": 1, "b": [2, 3]})

    os.environ["GEMINI_API_KEYS"] = "k1, k2"
    try:
        check("env keys override file", config.load_keys()["gemini_api_keys"] == ["k1", "k2"])
    finally:
        del os.environ["GEMINI_API_KEYS"]

    from trading_llm.server import auth_ok
    check("loopback always allowed", auth_ok("127.0.0.1", None, "secret") is True)
    check("remote without key blocked", auth_ok("10.0.0.5", None, "secret") is False)
    check("remote with key allowed", auth_ok("10.0.0.5", "secret", "secret") is True)
    check("remote, no key configured -> blocked", auth_ok("10.0.0.5", "x", "") is False)

    from trading_llm.brain.clients.openrouter_client import parse_free_models
    payload = {"data": [{"id": "a/b:free"}, {"id": "c/d"}, {"id": "e/f:free"}]}
    check("discovers free models", parse_free_models(payload) == ["a/b:free", "e/f:free"])

    from trading_llm.factors import clean_universe
    check("clean universe drops crypto/futures/dotted",
          clean_universe(["AAPL", "BTC/USD", "GC=F", "msft", "ETH-USD", "BRK.B"]) == ["AAPL", "MSFT"])

    from trading_llm.core.engine import TradingEngine
    check("remember-question is not saved", TradingEngine._memory_command(None, "remember when AAPL crashed?") is None)
    check("'how do i trade' is not a trade review", TradingEngine._wants_review(None, "how do i trade") is False)

    from trading_llm import gamify
    ids = [c["id"] for c in gamify.challenges({"equity": 100000, "portfolio_value": 100000}, [], 2000)]
    check("patience challenge added", "patience" in ids)


def test_safety(tmp: Path):
    print("[broker safety: mandate + kill-switch + guard + audit]")
    from trading_llm.broker import safety
    safety.HALT_FILE = tmp / "HALT"
    safety.AUDIT_PATH = tmp / "audit.json"
    m = {"enabled": True, "max_order_usd": 1000, "max_trades_per_day": 5, "allowed_symbols": []}
    buy = {"symbol": "AAPL", "action": "buy"}

    check("good order passes", safety.check_order(buy, 500, 0, m)[0] is True)
    check("disabled mandate blocks", safety.check_order(buy, 500, 0, {"enabled": False})[0] is False)
    check("over per-order cap blocks", safety.check_order(buy, 5000, 0, m)[0] is False)
    check("daily cap blocks", safety.check_order(buy, 100, 5, m)[0] is False)
    check("symbol allow-list blocks",
          safety.check_order({"symbol": "TSLA", "action": "buy"}, 100, 0,
                             {**m, "allowed_symbols": ["AAPL", "MSFT"]})[0] is False)

    safety.halt()
    check("kill-switch engaged", safety.is_halted() is True)
    check("kill-switch blocks orders", safety.check_order(buy, 100, 0, m)[0] is False)
    safety.resume()
    check("kill-switch cleared", safety.is_halted() is False)
    check("order passes after resume", safety.check_order(buy, 100, 0, m)[0] is True)

    safety.audit("test_event", {"x": 1})
    check("audit log records", any(e["action"] == "test_event" for e in safety.audit_log()))


def test_memory_notes_goals(tmp: Path):
    print("[memory: notes + research goals + commands]")
    from trading_llm.memory import notes, goals
    notes.NOTES_PATH = tmp / "notes.json"
    goals.GOALS_PATH = tmp / "goals.json"

    notes.add("I prefer swing trades on tech stocks")
    notes.add("Watching the Fed meeting on the 18th")
    check("two notes stored", len(notes.all_notes()) == 2)
    hits = notes.search("swing tech")
    check("search finds the swing note", bool(hits) and "swing" in hits[0]["text"].lower())
    check("notes format for prompt", "REMEMBERED NOTES" in notes.format_for_prompt("swing"))

    goals.add("Decide whether to buy NVDA this month")
    check("one active goal", len(goals.active()) == 1)
    check("goals format for prompt", "ACTIVE RESEARCH GOALS" in goals.format_for_prompt())
    check("complete goal", goals.complete() and len(goals.active()) == 0)

    # engine command parser (no engine construction needed — uses only module fns)
    from trading_llm.core.engine import TradingEngine
    mc = TradingEngine._memory_command(None, "remember I use 1% risk per trade")
    check("remember command saves note", mc and mc["provider"] == "memory" and "Noted" in mc["reply"])
    check("note count now 3", len(notes.all_notes()) == 3)
    g = TradingEngine._memory_command(None, "set a goal to master RSI divergence")
    check("set-goal command", g and g["provider"] == "goals" and len(goals.active()) == 1)
    check("non-command -> None", TradingEngine._memory_command(None, "how is NVDA today?") is None)


def test_debate_streaming():
    print("[debate: progress streaming]")
    from trading_llm.brain.debate import DebateEngine
    eng = DebateEngine(FakeRouter(FakeLLM("Rating: Hold\nBalanced read.")),
                       {"debate": {"research_rounds": 1, "risk_rounds": 1}})
    events = []
    res = eng.run("NVDA", "tech ctx", "news ctx", progress=lambda **e: events.append(e))
    stages = {e["stage"] for e in events}
    check("emits all stage groups", {"analysts", "research", "plan", "trader", "risk", "pm"} <= stages,
          str(stages))
    check("pm stage marked done", any(e["stage"] == "pm" and e["status"] == "done" for e in events))
    check("debate still returns result", res.rating == "Hold")


def _synth_panel(n_sym=8, n_days=320, seed=0):
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-02", periods=n_days, freq="B")
    syms = [f"S{i}" for i in range(n_sym)]
    rets = rng.normal(0.0005, 0.02, size=(n_days, n_sym))
    close = pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=idx, columns=syms)
    open_ = close.shift(1).bfill()
    high = close * (1 + np.abs(rng.normal(0, 0.006, size=close.shape)))
    low = close * (1 - np.abs(rng.normal(0, 0.006, size=close.shape)))
    vol = pd.DataFrame(rng.integers(1_000_000, 5_000_000, size=close.shape).astype(float),
                       index=idx, columns=syms)
    return {"open": open_, "high": high, "low": low, "close": close, "volume": vol,
            "returns": close.pct_change(), "_symbols": syms}


def test_factors():
    print("[factors: operators + IC bench + runner]")
    from trading_llm.factors import operators as op
    from trading_llm.factors import scoring as fb
    from trading_llm.factors import runner, explain
    import pandas as pd

    df = pd.DataFrame({"A": [1.0, 2, 3], "B": [3.0, 1, 2], "C": [2.0, 3, 1]})
    r = op.rank(df)
    check("cross-sectional rank in [0,1]", float(r.max().max()) <= 1.0 and float(r.min().min()) >= 0.0)
    check("delta lag>=1 enforced", _raises(lambda: op.delta(df, 0)))

    panel = _synth_panel()
    fwd = fb.forward_returns(panel["close"], 5)
    # a factor equal to forward returns must have near-perfect IC
    ic = fb.compute_ic_series(fwd, fwd)
    check("perfect factor -> IC ~ 1", ic.mean() > 0.99, str(round(ic.mean(), 3)))
    stats = fb.ic_stats(ic)
    check("ic_stats has IR + t-stat", "ir" in stats and "t_stat" in stats)
    spread = fb.quantile_spread(fwd, fwd)
    check("perfect factor -> positive spread", spread > 0, str(round(spread, 3)))
    strength, direction = fb.classify(0.05, 0.4)
    check("strong+momentum classification", strength == "strong" and direction == "momentum")

    # runner over a monkeypatched panel (no network)
    orig = runner.build_panel
    runner.build_panel = lambda *a, **k: panel
    try:
        res = runner.bench(period="1y", horizon=5)
    finally:
        runner.build_panel = orig
    check("bench ok with panel", res.ok, res.error)
    ok_results = [r for r in res.results if r.get("ok")]
    check("bench scored multiple factors", len(ok_results) >= 8, str(len(ok_results)))
    check("each result has IC + IR", all("ic_mean" in r and "ir" in r for r in ok_results))
    md = explain(res)
    check("factor explainer renders", "Factor scan" in md and "IC mean" in md)


def _raises(fn):
    try:
        fn()
        return False
    except Exception:
        return True


def test_skills():
    print("[learn: skill packs + retrieval]")
    from trading_llm.learn import skills
    from trading_llm.brain.prompts import BEGINNER_ADDENDUM
    packs = skills.load_all()
    check("loaded >= 14 skill packs", len(packs) >= 14, str(len(packs)))
    check("packs fully parsed", all(p.title and p.summary and p.body and p.tags for p in packs))
    rsi = skills.get("rsi")
    check("get('rsi') has body", rsi is not None and "overbought" in rsi.body.lower())
    rel = skills.find_relevant("what does RSI overbought mean")
    check("retrieval ranks rsi first", bool(rel) and rel[0].name == "rsi", str([p.name for p in rel]))
    rel2 = skills.find_relevant("how should I size my position and set a stop loss")
    check("retrieval finds risk-management", any(p.name == "risk-management" for p in rel2),
          str([p.name for p in rel2]))
    snip = skills.context_snippet(rel)
    check("context snippet has knowledge header", "RELEVANT KNOWLEDGE" in snip)
    check("cited returns name+title", skills.cited(rel)[0]["name"] == "rsi")
    check("beginner addendum present", "BEGINNER MODE" in BEGINNER_ADDENDUM)
    check("irrelevant query -> no packs", skills.find_relevant("xyzzy qwerty") == [])


def test_fill_realism(tmp: Path):
    print("[broker: fill realism — slippage + fees]")
    from trading_llm.broker import paper_broker
    paper_broker.ACCOUNT_PATH = tmp / "realism.json"
    b = paper_broker.PaperBroker(starting_cash=100000)
    pf = lambda s: 100.0

    r = b.place_order("AAPL", "buy", qty=10, price_fn=pf, slippage_bps=100, fee_bps=50)
    check("buy slips up to 101", abs(r["filled_avg_price"] - 101.0) < 1e-6, str(r["filled_avg_price"]))
    check("fee charged ~5.05", abs(r["fee"] - 5.05) < 0.01, str(r["fee"]))
    acct = b.get_account(pf)
    check("cash = 100000 - 1010 - 5.05", abs(acct["cash"] - 98984.95) < 0.02, str(acct["cash"]))

    r2 = b.place_order("MSFT", "buy", qty=1, price_fn=pf)  # defaults -> frictionless
    check("default frictionless fill", r2["filled_avg_price"] == 100.0 and r2["fee"] == 0.0)
    s = b.place_order("AAPL", "sell", qty=5, price_fn=pf, slippage_bps=100)
    check("sell slips down to 99", abs(s["filled_avg_price"] - 99.0) < 1e-6, str(s["filled_avg_price"]))


def test_optimize():
    print("[backtest: hyperparameter optimization]")
    from trading_llm.backtest import hyperopt as opt
    from trading_llm.backtest import data as btdata
    df = _synth_df(range(100, 220))
    orig = btdata.load_ohlc
    btdata.load_ohlc = lambda symbol, period="2y", interval="1d": df
    try:
        res = opt.optimize("AAPL", "sma_cross", grid={"fast": [5, 10], "slow": [20, 30]})
    finally:
        btdata.load_ohlc = orig
    check("optimize ok", res.ok, res.error)
    check("swept 4 combos (fast<slow)", res.n_combos == 4, str(res.n_combos))
    check("best_params has fast+slow", "fast" in res.best_params and "slow" in res.best_params)
    check("results ranked by metric", res.results[0]["metric_value"] >= res.results[-1]["metric_value"])
    check("reports out-of-sample metric", isinstance(res.oos_metric, float) and isinstance(res.overfit, bool))
    check("optimize explainer shows OOS", "out-of-sample" in opt.explain(res))


def test_strategy():
    print("[strategy builder: DSL + Pine + custom backtest]")
    import math
    from trading_llm.backtest import dsl, pine, custom
    from trading_llm.backtest import data as btdata

    spec = {"name": "RSI dip", "entry": {"all": [
                {"left": "rsi(14)", "op": "<", "right": 35},
                {"left": "close", "op": ">", "right": "sma(50)"}]},
            "exit": {"any": [{"left": "rsi(14)", "op": ">", "right": 60}]}}
    ok, err = dsl.validate(spec)
    check("valid spec validates", ok, err)
    check("bad operand rejected", dsl.validate(
        {"entry": {"all": [{"left": "frob(9)", "op": "<", "right": 1}]}, "exit": {"any": []}})[0] is False)

    df = _synth_df([100 + 20 * math.sin(i / 6) for i in range(200)])  # oscillates -> triggers
    sig = dsl.compile_signal(spec, df)
    check("signal is long/flat (0/1)", set(round(float(x), 1) for x in sig.unique()) <= {0.0, 1.0})

    p = pine.to_pine(spec)
    check("pine v6 + entry + indicator", "//@version=6" in p and "strategy.entry" in p and "ta.rsi(close, 14)" in p)
    pcross = pine.to_pine({"name": "x",
        "entry": {"all": [{"left": "ema(12)", "op": "crosses_above", "right": "ema(26)"}]},
        "exit": {"any": [{"left": "ema(12)", "op": "crosses_below", "right": "ema(26)"}]}})
    check("pine crossover -> ta.crossover", "ta.crossover" in pcross and "ta.crossunder" in pcross)

    orig = btdata.load_ohlc
    btdata.load_ohlc = lambda symbol, period="2y", interval="1d": df
    try:
        res = custom.run_custom(spec, "AAPL")
    finally:
        btdata.load_ohlc = orig
    check("custom backtest ok", res["ok"], res.get("error"))
    check("custom has metrics + curve + pine", "metrics" in res and len(res["equity_curve"]) > 0 and res.get("pine"))
    check("custom explanation renders", "Custom strategy" in res["explanation"] and "Pine Script" in res["explanation"])


def test_shadow():
    print("[shadow account + gamification]")
    from trading_llm.shadow import trades as T
    from trading_llm.shadow import analyze, report
    from trading_llm import gamify

    fills = [
        {"ts": "2026-01-01T10:00:00", "symbol": "AAPL", "side": "buy", "qty": 10, "price": 100.0},
        {"ts": "2026-01-05T10:00:00", "symbol": "AAPL", "side": "sell", "qty": 10, "price": 110.0},
        {"ts": "2026-01-02T10:00:00", "symbol": "MSFT", "side": "buy", "qty": 5, "price": 200.0},
        {"ts": "2026-01-20T10:00:00", "symbol": "MSFT", "side": "sell", "qty": 5, "price": 180.0},
    ]
    trips = T.pair_trades(fills)
    check("paired 2 round-trips", len(trips) == 2, str(len(trips)))
    aapl = next(t for t in trips if t.symbol == "AAPL")
    check("AAPL long win pnl=100", aapl.side == "long" and abs(aapl.pnl - 100) < 1e-6, str(aapl.pnl))
    check("MSFT loss pnl=-100", abs(next(t for t in trips if t.symbol == "MSFT").pnl + 100) < 1e-6)

    short = T.pair_trades([
        {"ts": "2026-02-01", "symbol": "NVDA", "side": "sell", "qty": 2, "price": 500.0},
        {"ts": "2026-02-02", "symbol": "NVDA", "side": "buy", "qty": 2, "price": 480.0}])
    check("short profits when price falls", bool(short) and short[0].side == "short" and short[0].pnl > 0)

    prof = analyze(trips)
    check("win rate 50%", prof["win_rate_pct"] == 50.0, str(prof["win_rate_pct"]))
    check("disposition effect flagged", any(b["name"] == "Disposition effect" for b in prof["biases"]))
    check("shadow report renders", "Trade review" in report(prof))
    check("empty analyze -> ok False", analyze([])["ok"] is False)

    acct = {"equity": 100000.0, "portfolio_value": 100000.0}
    sc = gamify.scorecard(acct, trips, 2000)
    check("scorecard graded", sc["ok"] and sc["grade"] in ("A", "B", "C", "D", "F"), str(sc.get("grade")))
    chs = gamify.challenges(acct, trips, 2000)
    check("first-trade challenge done", any(c["id"] == "first_trade" and c["done"] for c in chs))
    coach_md = gamify.coach_report(acct, trips, 2000)
    check("coach report renders", "trading coach" in coach_md and "Challenges" in coach_md)


def test_signals(tmp: Path):
    print("[signals: regime + insider/13F/congress parsing + service fail-soft]")
    from datetime import date, datetime
    from trading_llm.signals import (
        SignalBundle, detect_regime, signal_format, INSIDER_SELL, INST_13F, CONGRESS,
    )
    from trading_llm.signals import edgar, congress as congress_mod, regime as regmod
    from trading_llm.signals import service as svc

    fix = ROOT / "tests" / "fixtures" / "signals"

    # --- regime pure helpers / classification ---
    up = [100 * (1.0008 ** i) for i in range(260)]
    down = [100 * (0.999 ** i) for i in range(260)]
    check("trend up classified", regmod.classify_trend(regmod.pct_vs_sma(up, 200)) == "up")
    check("trend down classified", regmod.classify_trend(regmod.pct_vs_sma(down, 200)) == "down")
    check("vol low on smooth series", regmod.classify_vol(regmod.realized_vol(up, 20)) == "low")
    check("label risk_on", regmod.classify_label("up", 70, "normal", 5.0) == "risk_on")
    check("label risk_off (downtrend)", regmod.classify_label("down", 70, "normal", 5.0) == "risk_off")
    check("label risk_off (high vol + neg mom)", regmod.classify_label("up", 40, "high", -3.0) == "risk_off")
    check("label neutral", regmod.classify_label("sideways", 50, "normal", 1.0) == "neutral")

    class FakeData:
        def get_bars(self, sym, tf="1Day", n=120):
            return up[-n:]
    reg = detect_regime(FakeData(), universe=["AAA", "BBB", "CCC", "DDD", "EEE"])
    check("detect_regime ok + risk_on", reg.ok and reg.label == "risk_on", reg.label)
    check("regime_summary renders", signal_format.regime_summary(reg).startswith("Regime: RISK-ON"))

    class NoData:
        def get_bars(self, sym, tf="1Day", n=120):
            return []
    check("regime fail-soft (no data -> ok False)", detect_regime(NoData()).ok is False)

    # --- Form 4 parse (real fixture) ---
    f4 = (fix / "form4_sample.xml").read_text(encoding="utf-8")
    sigs = edgar.parse_form4(f4, as_of="2026-06-14", source_url="http://x")
    check("form4 parses one transaction", len(sigs) == 1, str(len(sigs)))
    check("form4 is a sell of AAPL", sigs[0].kind == INSIDER_SELL and sigs[0].symbol == "AAPL")
    check("form4 size_usd = shares*price", abs(sigs[0].size_usd - 50000 * 311.02) < 1, str(sigs[0].size_usd))
    check("form4 owner labeled", "Levinson" in sigs[0].actor and "Director" in sigs[0].actor)
    check("form4 bad xml -> []", edgar.parse_form4("<not xml") == [])

    # --- 13F parse ---
    t13 = (fix / "form13f_sample.xml").read_text(encoding="utf-8")
    holds = edgar.parse_13f(t13)
    check("13f parses 6 holdings", len(holds) == 6, str(len(holds)))
    check("13f value + shares parsed", holds[0]["value_usd"] > 0 and holds[0]["shares"] > 0)
    index = {"AAPL": [{"filer": "Berkshire Hathaway", "value_usd": 5e9, "report_date": "2026-03-31", "url": "u"}]}
    f_sigs, funds = edgar.signals_from_holdings("AAPL", index, "2026-06-14")
    check("signals_from_holdings -> 1 fund", funds == 1 and f_sigs[0].kind == INST_13F)

    # --- congress parse (lookback filtering) ---
    cj = (fix / "congress_sample.json").read_text(encoding="utf-8")
    cs = congress_mod.parse_congress(cj, as_of="2026-06-14", now=datetime(2026, 6, 14), lookback_days=365)
    check("congress parses 2 (old row filtered)", len(cs) == 2, str(len(cs)))
    check("congress dir + amount midpoint", cs[0].kind == CONGRESS and cs[0].size_usd == 8000.5, str(cs[0].size_usd))
    check("congress bad json -> []", congress_mod.parse_congress("nope") == [])

    # --- SignalBundle aggregation ---
    b = SignalBundle.build("AAPL", sigs + cs, funds_holding=3, now=date(2026, 6, 14))
    check("bundle nets insider sell (negative)", b.net_insider_usd_30d < 0, str(b.net_insider_usd_30d))
    check("bundle counts sells", b.insider_sells_30d == 1 and b.insider_buys_30d == 0)
    check("bundle funds_holding", b.funds_holding == 3)
    check("bundle congress 90d", b.congress_trades_90d == 2)
    check("signals_summary non-empty", "insiders" in signal_format.signals_summary(b))

    # --- service: cache round-trip + fail-soft (no network) ---
    svc._CACHE_DIR = tmp / "sig_cache"
    settings = {"signals": {"enabled": True, "sec_user_agent": "test", "cache_ttl_hours": 12,
                            "sources": {"insiders": True, "institutional_13f": False, "congress": False},
                            "famous_filers": []}}
    service = svc.SignalService(FakeData(), settings, warm=False)
    service._write("insider_AAPL", [s.to_dict() for s in sigs])
    cached = service.cached_bundle("AAPL")
    check("service cache round-trips signals", len(cached.signals) == 1 and cached.signals[0].symbol == "AAPL")

    def boom(*a, **k):
        raise RuntimeError("SEC down")
    orig = edgar.fetch_insider_signals
    edgar.fetch_insider_signals = boom
    try:
        safe = service.signals_for("TSLA", allow_fetch=True)  # must not raise
        check("service fail-soft on source error", safe.symbol == "TSLA")
    finally:
        edgar.fetch_insider_signals = orig

    # --- snapshot integration ---
    from trading_llm.market import snapshot

    class SnapData:
        def market_open(self):
            return True
        def get_bars(self, sym, tf="1Day", n=120):
            return up[-n:]
        def get_price(self, sym):
            return up[-1]
        def sources(self):
            return ["yfinance"]

    class FakeService:
        def cached_regime(self):
            return reg
        def cached_bundle(self, sym):
            return b
    txt = snapshot.build_snapshot(SnapData(), ["AAPL"], "1Day", 60,
                                  include_news=False, signal_service=FakeService())
    check("snapshot includes regime line", "[MARKET REGIME]" in txt)
    check("snapshot includes smart-money tag", "smart-money:" in txt)


def test_eventstudy():
    print("[event study: forward returns + edge + t-stat + IS/OOS verdict]")
    from datetime import date, timedelta
    from trading_llm.signals import eventstudy as es

    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(450)]
    spy = [100.0] * 450
    ev_idx = [20 + 28 * k for k in range(12)]
    events = [{"date": str(dates[i])} for i in ev_idx]

    # a signal that "works": +5% permanent step the day after each event
    works, lvl, steps = [], 100.0, {i + 1 for i in ev_idx}
    for i in range(450):
        if i in steps:
            lvl *= 1.05
        works.append(lvl)

    r1 = es.event_study(events, dates, works, dates, spy, horizons=(30, 60, 90))
    row30 = next(r for r in r1["horizons"] if r["horizon"] == 30)
    check("works: positive edge", row30["edge_pct"] > 0, str(row30["edge_pct"]))
    check("works: significant t-stat", row30["t_stat"] > 2, str(row30["t_stat"]))
    check("works: verdict positive", "positive" in r1["verdict"].lower())

    r2 = es.event_study(events, dates, list(spy), dates, spy)  # stock == SPY -> no alpha
    row60 = next(r for r in r2["horizons"] if r["horizon"] == 60)
    check("noise: ~zero edge", abs(row60["edge_pct"]) < 0.5, str(row60["edge_pct"]))
    check("noise: verdict says noise", "noise" in r2["verdict"].lower())

    check("forward_return None past end", es.forward_return(dates, works, dates[-1], 30) is None)
    check("forward_return None empty", es.forward_return([], [], dates[0], 30) is None)

    r3 = es.event_study(events[:5], dates, works, dates, spy)
    check("too-few-events verdict", "few" in r3["verdict"].lower() or "anecdote" in r3["verdict"].lower())
    check("explain renders", es.explain(r1).startswith("**12 events**"))
    check("study no events -> ok False", es.event_study([], dates, works, dates, spy)["ok"] is False)


def test_phase_c(tmp: Path):
    print("[phase C: smart-money analyst + act/learn loop]")
    # --- C1: analyst joins the committee when signals_context is provided ---
    from trading_llm.brain.debate import DebateEngine
    fake = FakeLLM("Rating: Buy\nConstructive; insiders supportive.")
    eng = DebateEngine(FakeRouter(fake), {"debate": {"research_rounds": 1, "risk_rounds": 1}})
    res = eng.run("NVDA", "RSI 55 trend up", "- bullish headline",
                  signals_context="Regime: RISK-ON. Smart money on NVDA: insiders +$5M (3 buys/30d).")
    check("smart-money analyst ran (11 calls)", fake.calls == 11, str(fake.calls))
    check("smart_money_report populated", bool(res.smart_money_report))
    check("transcript has smart_money_report", "smart_money_report" in res.transcript)
    check("markdown shows smart-money section", "Smart-money" in res.to_markdown())
    check("analyst saw the signals context", any("insiders +$5M" in str(p) for p in fake.prompts))

    # backward compatible: no signals_context -> no extra call (still 10)
    fake2 = FakeLLM("Rating: Hold\nBalanced.")
    DebateEngine(FakeRouter(fake2), {"debate": {"research_rounds": 1, "risk_rounds": 1}}).run(
        "AAPL", "tech", "news")
    check("no analyst without context (10 calls)", fake2.calls == 10, str(fake2.calls))

    # --- C3: learning loop record -> resolve -> base rates ---
    from trading_llm.signals import learning
    learning.JOURNAL_PATH = tmp / "signal_journal.json"
    learning.record("AAPL", "insider_buy", "risk_on", decision_date="2024-01-02", side="buy")
    learning.record("NVDA", "insider_buy", "risk_on", decision_date="2024-01-03", side="buy")
    learning.record("XOM", "insider_buy", "risk_off", decision_date="2024-01-04", side="buy")

    def fake_fetch(sym, date, holding_days=60):
        return {"AAPL": (0.08, 0.03, 60), "NVDA": (0.10, 0.05, 60),
                "XOM": (-0.04, -0.02, 60)}[sym]
    check("resolve_pending resolves matured", learning.resolve_pending(60, fetch=fake_fetch) == 3)
    check("resolve is idempotent", learning.resolve_pending(60, fetch=fake_fetch) == 0)
    br = learning.base_rates()
    check("overall base rate", br["overall"]["n"] == 3 and br["overall"]["wins"] == 2)
    check("risk_on group 100% win", br["by_group"]["insider_buy|risk_on"]["win_rate_pct"] == 100.0)
    check("risk_off group 0 wins", br["by_group"]["insider_buy|risk_off"]["wins"] == 0)
    tr = learning.track_record_context()
    check("track-record context renders", "DESK TRACK RECORD" in tr and "beat SPY" in tr)

    # pending entry (recent) isn't resolved
    learning.record("MSFT", "insider_buy", "risk_on", side="buy")  # today -> pending
    check("recent entry stays pending", learning.base_rates()["pending"] == 1)

    # --- C2: signal_ideas shape + proposal carries the signal tag ---
    from trading_llm.signals.models import SignalBundle, Signal, INSIDER_BUY
    class FakeSignals:
        enabled = True
        def cached_regime(self):
            from trading_llm.signals.models import Regime
            return Regime(ok=True, label="risk_on")
        def signals_for(self, sym, allow_fetch=True):
            if sym == "AAPL":
                s = Signal(kind=INSIDER_BUY, symbol="AAPL", date="2026-06-01", actor="CEO",
                           direction=1, size_usd=3_000_000)
                return SignalBundle.build("AAPL", [s], funds_holding=2)
            return SignalBundle.build(sym, [])
    from trading_llm.core.engine import TradingEngine
    eng2 = object.__new__(TradingEngine)  # bypass __init__/network
    eng2.signals = FakeSignals()
    eng2.settings = {"risk": {"max_position_usd": 2000}}
    eng2.watchlist = ["AAPL", "MSFT"]
    out = eng2.signal_ideas(scan_cap=2)
    check("ideas finds the insider-buy name", any(i["symbol"] == "AAPL" for i in out["ideas"]))
    idea = next(i for i in out["ideas"] if i["symbol"] == "AAPL")
    check("idea proposal tagged signal_idea", idea["proposal"]["source"] == "signal_idea"
          and idea["proposal"]["signal_kind"] == "insider_buy")
    check("idea sized to 25% of max_pos", idea["proposal"]["notional"] == 500)
    check("TradeIn carries source", "source" in __import__("trading_llm.server", fromlist=["TradeIn"]).TradeIn.model_fields)


def test_risk():
    print("[risk: sizing, Kelly, risk-of-ruin, portfolio heat, pre-trade check]")
    from trading_llm.risk import sizing as rk

    check("expectancy", rk.expectancy(0.5, 2.0) == 0.5)
    check("kelly half-edge", abs(rk.kelly_fraction(0.5, 2.0) - 0.25) < 1e-9)
    check("kelly negative-edge -> 0", rk.kelly_fraction(0.4, 0.5) == 0.0)
    check("suggested = quarter-kelly capped", rk.suggested_risk_pct(0.6, 2.0) <= 0.02)

    s = rk.fixed_fractional_size(100000, 0.01, 100, 90)
    check("size shares", s["shares"] == 100, str(s))
    check("size risk dollars", s["risk_dollars"] == 1000.0)
    check("size no-stop guard", rk.fixed_fractional_size(100000, 0.01, 100, 100)["shares"] == 0)

    atr = rk.atr_from_bars([11, 12, 13, 14, 15], [9, 10, 11, 12, 13], [10, 11, 12, 13, 14], period=2)
    check("ATR computes", atr is not None and atr > 0)
    check("ATR insufficient -> None", rk.atr_from_bars(None, None, [1, 2], period=14) is None)

    lo = rk.risk_of_ruin(0.5, 1.5, 0.02, sims=1200, seed=3)
    hi = rk.risk_of_ruin(0.5, 1.5, 0.10, sims=1200, seed=3)
    check("ruin rises with risk size", hi > lo, f"{lo} vs {hi}")
    check("ruin zero at zero risk", rk.risk_of_ruin(0.5, 1.5, 0.0) == 0.0)

    h = rk.portfolio_heat([{"market_value": 20000}, {"market_value": 10000}], 100000, stop_pct=0.10)
    check("heat gross %", h["gross_pct"] == 30.0)
    check("heat open-risk %", h["open_risk_pct"] == 3.0)

    over = rk.pretrade_check({"action": "buy", "symbol": "X", "notional": 5000}, 100000, 100000, [],
                            {"max_position_usd": 2000})
    check("pretrade fails oversize", over["verdict"] == "fail")
    okc = rk.pretrade_check({"action": "buy", "symbol": "X", "notional": 1500, "rationale": "stop 90"},
                           100000, 100000, [], {"max_position_usd": 2000})
    check("pretrade passes good order", okc["verdict"] == "pass")
    poor = rk.pretrade_check({"action": "buy", "symbol": "X", "notional": 1500}, 100000, 500, [],
                            {"max_position_usd": 2000})
    check("pretrade fails low buying power", poor["verdict"] == "fail")
    check("pretrade has stop warning",
          any(c["name"] == "Stop defined" and c["status"] == "warn" for c in over["checks"]))


def test_edge():
    print("[edge: seasonality, squeeze, options flow, PEAD]")
    from datetime import date, timedelta
    from trading_llm.edge import seasonality as sea, short_interest as si, options_flow as of, pead

    # seasonality: 4y, January reliably strong
    dates, closes, lvl, d = [], [], 100.0, date(2021, 1, 1)
    while d <= date(2024, 12, 31):
        if d.weekday() < 5:
            lvl *= 1.003 if d.month == 1 else 1.0002
            dates.append(d); closes.append(lvl)
        d += timedelta(days=1)
    s = sea.analyze(dates, closes, now_month=1)
    check("seasonality ok", s["ok"])
    check("January is best month", s["best_month"]["name"] == "Jan", str(s["best_month"]))
    check("seasonality needs history", sea.analyze([date(2024, 1, 1)], [100.0])["ok"] is False)

    # squeeze score
    check("squeeze max at extremes", si.squeeze_score(40, 10) == 100)
    check("squeeze zero at none", si.squeeze_score(0, 0) == 0)
    check("squeeze monotonic", si.squeeze_score(30, 8) > si.squeeze_score(5, 1))

    # options summary
    calls = [{"strike": 100, "volume": 5000, "openInterest": 100, "impliedVolatility": 0.30, "lastPrice": 3},
             {"strike": 105, "volume": 50, "openInterest": 1000, "impliedVolatility": 0.28, "lastPrice": 1}]
    puts = [{"strike": 100, "volume": 200, "openInterest": 2000, "impliedVolatility": 0.32, "lastPrice": 2}]
    o = of.summarize_chain(calls, puts, spot=100)
    check("put/call vol ratio", o["put_call_volume_ratio"] == round(200 / 5050, 2))
    check("ATM IV averaged", o["atm_iv_pct"] == 31.0, str(o["atm_iv_pct"]))
    check("unusual flagged", any(u["strike"] == 100 and u["side"] == "call" for u in o["unusual"]))
    check("options empty -> no flow", of.summarize_chain([], [], 0)["sentiment"] == "no flow")

    # PEAD
    dts = [date(2023, 1, 1) + timedelta(days=i) for i in range(400)]
    cl = [100.0] * 400

    def bump(start, rxn, drift):
        cl[start] = cl[start - 1] * (1 + rxn)
        for k in range(1, 21):
            cl[start + k] = cl[start] * (1 + drift * k / 20)
    bump(50, 0.05, 0.08); bump(149, 0.06, 0.07); bump(249, -0.05, -0.06)
    rx = pead.earnings_reactions([dts[50], dts[149], dts[249]], dts, cl, drift_days=20)
    check("PEAD reactions aligned", rx[0]["reaction_pct"] == 5.0, str(rx[0]))
    summ = pead.summarize_pead(rx)
    check("PEAD buckets", summ["n_pos"] == 2 and summ["n_neg"] == 1)
    check("PEAD detected", summ["has_pead"] is True)


def test_scanner():
    print("[scanner: composite score + transparent breakdown]")
    from trading_llm.scanner import composite as cp

    bull = cp.score_symbol({"trend": "up", "rsi": 65, "momentum": "bullish", "price_vs_sma50_pct": 8,
                            "net_insider_30d": 4_000_000, "funds_holding": 4,
                            "seasonality_month_pct": 2.5, "squeeze_score": 40})
    check("all-bullish -> high score", bull["score"] > 58 and bull["direction"] == "bullish", str(bull["score"]))
    bear = cp.score_symbol({"trend": "down", "rsi": 35, "momentum": "bearish",
                            "price_vs_sma50_pct": -8, "net_insider_30d": -3_000_000})
    check("all-bearish -> low score", bear["score"] < 42 and bear["direction"] == "bearish", str(bear["score"]))

    part = cp.score_symbol({"trend": "up", "rsi": 60, "momentum": "bullish", "price_vs_sma50_pct": 5})
    check("partial renormalizes weights", part["available"] == ["momentum"]
          and abs(sum(c["weight"] for c in part["components"]) - 1.0) < 1e-6)
    empty = cp.score_symbol({})
    check("no data -> neutral 50", empty["score"] == 50.0 and empty["n_components"] == 0)

    # contributions reconstruct the score (transparency)
    recon = 50 + sum(c["points"] for c in bull["components"])
    check("breakdown reconstructs score", abs(recon - bull["score"]) < 0.3, f"{recon} vs {bull['score']}")
    # insider sign respected
    pos = cp.score_symbol({"net_insider_30d": 5_000_000})
    neg = cp.score_symbol({"net_insider_30d": -5_000_000})
    check("insider sign drives direction", pos["score"] > 50 > neg["score"])


def test_alerts(tmp: Path):
    print("[alerts: rule eval + store + walk-forward backtest]")
    from datetime import date, timedelta
    from trading_llm.alerts import rules as R, store as S, walkforward as WF

    feats = {"rsi": 28, "trend": "up", "composite": 64, "regime": "risk_on"}
    conds = [{"field": "rsi", "op": "<=", "value": 35}, {"field": "trend", "op": "==", "value": "up"}]
    check("AND-conditions fire", R.evaluate_conditions(conds, feats) is True)
    check("one false -> no fire", R.evaluate_conditions(conds, {"rsi": 50, "trend": "up"}) is False)
    check("empty rule never fires", R.evaluate_conditions([], feats) is False)
    check("missing feature -> no fire", R.evaluate_conditions([{"field": "rsi", "op": "<=", "value": 35}], {}) is False)

    ok, fwd = R.is_backtestable({"conditions": conds})
    check("price rule is backtestable", ok and not fwd)
    ok2, fwd2 = R.is_backtestable({"conditions": [{"field": "composite", "op": ">=", "value": 60}]})
    check("smart-money rule is forward-only", (not ok2) and fwd2 == ["composite"])

    S.RULES_PATH = tmp / "alert_rules.json"
    check("presets seed", len(S.list_rules()) == 3)
    saved = S.save_rule({"name": "RSI dip", "conditions": conds, "hold_days": 15})
    check("save adds id", bool(saved.get("id")) and any(r["id"] == saved["id"] for r in S.list_rules()))
    S.save_rule({**saved, "name": "renamed"})
    check("save updates in place", any(r["name"] == "renamed" for r in S.list_rules())
          and len(S.list_rules()) == 4)
    check("delete works", S.delete_rule(saved["id"]) is True and len(S.list_rules()) == 3)

    # walk-forward: sawtooth so RSI<=35 dips precede a bounce
    dts = [date(2022, 1, 1) + timedelta(days=i) for i in range(700)]
    closes, lvl = [], 100.0
    for i in range(700):
        lvl *= 0.985 if (i % 30) < 10 else 1.012
        closes.append(lvl)
    spy = [100.0] * 700
    res = WF.backtest({"conditions": [{"field": "rsi", "op": "<=", "value": 35}], "hold_days": 15},
                      dts, closes, dts, spy)
    check("walk-forward runs on price rule", res["ok"] and res.get("n_entries", 0) >= 1, str(res.get("reason")))
    check("walk-forward has event-study stats", bool(res.get("horizons")))
    res2 = WF.backtest({"conditions": [{"field": "composite", "op": ">=", "value": 60}], "hold_days": 20},
                       dts, closes, dts, spy)
    check("forward-only rule can't backtest", res2["ok"] is False and "composite" in res2.get("skipped_forward_only", []))


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_indicators()
        test_memory(tmp)
        test_decision_log(tmp)
        test_paper_broker(tmp)
        test_data_helpers()
        test_trade_parsing(tmp)
        test_provider_router()
        test_gemini_contents()
        test_signal()
        test_debate_pipeline()
        test_debate_unavailable()
        test_reflection(tmp)
        test_backtest()
        test_fill_realism(tmp)
        test_optimize()
        test_strategy()
        test_factors()
        test_skills()
        test_shadow()
        test_agentic()
        test_hardening(tmp)
        test_safety(tmp)
        test_memory_notes_goals(tmp)
        test_debate_streaming()
        test_signals(tmp)
        test_eventstudy()
        test_phase_c(tmp)
        test_risk()
        test_edge()
        test_scanner()
        test_alerts(tmp)
    print("\n" + "=" * 40)
    print(f"  {_passed} passed, {_failed} failed")
    print("=" * 40)
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
