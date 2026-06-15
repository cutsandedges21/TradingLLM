"""FastAPI backend for the Trading LLM web UI.

Wraps the TradingEngine and serves the built React frontend (web/dist). Same
brain, data, broker, and memory — a modern face over HTTP. This is the single
interface for v2 (the Tkinter desktop UI was retired in Phase 0).
"""
from __future__ import annotations

import json
import queue
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fastapi import Request
from fastapi.responses import JSONResponse

from trading_llm.core.paths import WEB_DIST
from trading_llm.core.engine import TradingEngine
from trading_llm.core.config import api_auth_key

engine = TradingEngine()
app = FastAPI(title="Trading LLM")

# Allow the Vite dev server (5173) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_LOOPBACK = {"127.0.0.1", "::1", "localhost", None}


def _bearer(header: str | None) -> str | None:
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def auth_ok(client_host: str | None, provided: str | None, configured: str) -> bool:
    """Local (loopback) access is always allowed; remote access requires the key.

    If no key is configured, remote access is refused outright (localhost-only).
    """
    if client_host in _LOOPBACK:
        return True
    if not configured:
        return False
    return bool(provided) and provided == configured


@app.middleware("http")
async def _api_auth(request: Request, call_next):
    if request.url.path.startswith("/api"):
        host = request.client.host if request.client else None
        provided = request.headers.get("x-api-key") or _bearer(request.headers.get("authorization"))
        if not auth_ok(host, provided, api_auth_key()):
            return JSONResponse(
                {"error": "Unauthorized. Remote API access requires an X-API-Key header "
                          "(set TRADING_LLM_API_KEY or api_auth_key in settings)."},
                status_code=401)
    return await call_next(request)


class ChatIn(BaseModel):
    message: str
    deep: bool = False


class TradeIn(BaseModel):
    action: str
    symbol: str
    qty: float | None = None
    notional: float | None = None
    order_type: str = "market"
    limit_price: float | None = None
    rationale: str = ""
    source: str | None = None        # e.g. "signal_idea" → tagged for the learning loop
    signal_kind: str | None = None


class SettingsIn(BaseModel):
    watchlist: list[str] | None = None
    mock_starting_cash: float | None = None


class ResetIn(BaseModel):
    cash: float | None = None


class DeleteOrderIn(BaseModel):
    ts: str
    symbol: str | None = None


class BrainIn(BaseModel):
    mode: str


class BeginnerIn(BaseModel):
    on: bool


class AgentIn(BaseModel):
    message: str


class MandateIn(BaseModel):
    enabled: bool | None = None
    max_order_usd: float | None = None
    max_trades_per_day: int | None = None
    allowed_symbols: list[str] | None = None


class HaltIn(BaseModel):
    on: bool


class AlertRuleIn(BaseModel):
    id: str | None = None
    name: str
    conditions: list[dict] = []
    scope: str = "universe"
    symbols: list[str] = []
    action: str = "buy"
    hold_days: int = 20
    risk_pct: float = 0.01
    enabled: bool = True


class AlertDeleteIn(BaseModel):
    id: str


class AlertBacktestIn(BaseModel):
    rule: dict
    symbol: str | None = None


class RiskSizeIn(BaseModel):
    symbol: str
    entry: float | None = None
    stop: float | None = None
    risk_pct: float | None = None
    method: str = "fixed"


class BacktestIn(BaseModel):
    symbol: str
    strategy: str = "sma_cross"
    params: dict | None = None
    period: str = "2y"
    interval: str = "1d"


class FactorBenchIn(BaseModel):
    universe: list[str] | None = None
    period: str = "2y"
    horizon: int = 5
    factors: list[str] | None = None


class OptimizeIn(BaseModel):
    symbol: str
    strategy: str = "sma_cross"
    period: str = "2y"
    interval: str = "1d"
    metric: str = "sharpe"


class StrategyGenIn(BaseModel):
    description: str
    symbol: str | None = None
    period: str | None = None


class StrategyRunIn(BaseModel):
    spec: dict
    symbol: str = "SPY"
    period: str = "2y"


class ShadowUploadIn(BaseModel):
    csv: str


# Chart timeframe -> (yfinance period, interval). 1m is yfinance's floor.
CHART_TF = {
    "1M": ("5d", "1m"),
    "5M": ("5d", "5m"),
    "15M": ("1mo", "15m"),
    "1H": ("3mo", "1h"),
    "1D": ("1y", "1d"),
    "1W": ("5y", "1wk"),
}


@app.get("/api/status")
def status():
    return engine.status()


@app.get("/api/account")
def account():
    return engine.account() or {}


@app.get("/api/positions")
def positions():
    return engine.positions()


@app.get("/api/watchlist")
def watchlist():
    return engine.watchlist_rows()


@app.get("/api/bars/{symbol:path}")
def bars(symbol: str):
    closes = engine.data.get_bars(symbol, engine.timeframe, engine.lookback)
    return {"symbol": symbol, "closes": closes}


@app.get("/api/learn")
def learn():
    return {"markdown": engine.learn_text()}


@app.get("/api/orders")
def orders():
    from trading_llm.memory import journal
    return journal.recent(30, entry_type="trade")


@app.post("/api/orders/delete")
def delete_order(inp: DeleteOrderIn):
    from trading_llm.memory import journal
    return {"ok": journal.delete_trade(inp.ts, inp.symbol)}


@app.post("/api/chat")
def chat(inp: ChatIn):
    res = engine.ask(inp.message, deep=inp.deep)
    if res.get("proposal"):
        res["proposal"]["est_cost"] = engine.estimate_cost(res["proposal"])
    return res


@app.post("/api/agent")
def agent(inp: AgentIn):
    res = engine.agent_ask(inp.message)
    if res.get("proposal"):
        res["proposal"]["est_cost"] = engine.estimate_cost(res["proposal"])
    return res


@app.post("/api/chat/stream")
def chat_stream(inp: ChatIn):
    """Server-Sent Events: streams committee progress for deep analysis, then the result."""
    q: queue.Queue = queue.Queue()

    def work():
        try:
            engine.stream_chat(inp.message, inp.deep, lambda ev: q.put(ev))
        except Exception as exc:  # noqa: BLE001
            q.put({"type": "error", "error": str(exc)})
        finally:
            q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def gen():
        while True:
            ev = q.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/trade")
def trade(inp: TradeIn):
    return engine.place_trade(inp.model_dump())


@app.post("/api/reset")
def reset(inp: ResetIn):
    acct = engine.reset_account(inp.cash)
    return {"ok": True, "account": acct}


@app.get("/api/quotes")
def quotes(symbols: str = ""):
    syms = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else engine.watchlist
    return engine.quotes(syms)


SUBMINUTE_TF = {"1S", "5S", "30S"}


@app.get("/api/candles/{symbol:path}")
def candles(symbol: str, tf: str = "1D"):
    from trading_llm.market.data import is_crypto
    tfu = tf.upper()
    # Crypto -> Binance (real sub-minute history). Falls back to yfinance/live if blocked.
    if is_crypto(symbol):
        cs = engine.data.get_crypto_ohlc(symbol, tfu)
        if cs or tfu in SUBMINUTE_TF:
            return {"symbol": symbol, "tf": tfu, "candles": cs, "source": "binance" if cs else "live"}
    if tfu in SUBMINUTE_TF:
        # stocks/futures have no free sub-minute history -> client builds it live
        return {"symbol": symbol, "tf": tfu, "candles": [], "source": "live"}
    period, interval = CHART_TF.get(tfu, ("1y", "1d"))
    return {"symbol": symbol, "tf": tfu, "candles": engine.data.get_ohlc(symbol, period, interval),
            "source": "yfinance"}


@app.get("/api/tick/{symbol:path}")
def tick(symbol: str):
    """Uncached latest price — drives the live 5s/30s tick chart."""
    return {"symbol": symbol, "price": engine.data.get_price_fresh(symbol)}


@app.get("/api/settings")
def get_settings():
    return engine.get_settings()


@app.post("/api/settings")
def post_settings(inp: SettingsIn):
    patch = {k: v for k, v in inp.model_dump().items() if v is not None}
    return engine.update_settings(patch)


@app.post("/api/brain")
def set_brain(inp: BrainIn):
    return engine.set_brain_mode(inp.mode)


@app.get("/api/strategies")
def strategies():
    from trading_llm.backtest import list_strategies
    return list_strategies()


@app.post("/api/backtest")
def backtest_ep(inp: BacktestIn):
    return engine.backtest_spec(inp.model_dump())


@app.post("/api/optimize")
def optimize_ep(inp: OptimizeIn):
    return engine.optimize_spec(inp.model_dump())


@app.post("/api/strategy/generate")
def strategy_generate(inp: StrategyGenIn):
    return engine.generate_strategy(inp.description, inp.symbol, inp.period)


@app.post("/api/strategy/run")
def strategy_run(inp: StrategyRunIn):
    return engine.custom_backtest(inp.spec, inp.symbol, inp.period)


@app.post("/api/strategy/pine")
def strategy_pine(inp: StrategyRunIn):
    return engine.strategy_pine(inp.spec)


@app.post("/api/beginner")
def set_beginner(inp: BeginnerIn):
    return engine.set_beginner_mode(inp.on)


@app.get("/api/skills")
def skills_list():
    return engine.list_skills()


@app.get("/api/skills/{name}")
def skill_get(name: str):
    pack = engine.get_skill(name)
    return pack or {"error": "not found"}


@app.get("/api/factors")
def factors():
    from trading_llm.factors import list_factors
    return list_factors()


@app.post("/api/factors/bench")
def factors_bench(inp: FactorBenchIn):
    return engine.factor_bench(inp.model_dump())


@app.get("/api/risk/dashboard")
def risk_dashboard():
    return engine.risk_dashboard()


@app.post("/api/risk/size")
def risk_size(inp: RiskSizeIn):
    return engine.position_size(inp.symbol, inp.entry, inp.stop, inp.risk_pct, inp.method)


@app.post("/api/risk/check")
def risk_check(inp: TradeIn):
    return engine.risk_check(inp.model_dump())


@app.get("/api/scanner")
def scanner():
    return engine.scan_universe()


@app.get("/api/alerts/fields")
def alert_fields():
    return engine.alert_fields()


@app.get("/api/alerts/rules")
def alert_rules_list():
    return engine.list_alert_rules()


@app.post("/api/alerts/rules")
def alert_rule_save(inp: AlertRuleIn):
    return engine.save_alert_rule({k: v for k, v in inp.model_dump().items() if not (k == "id" and v is None)})


@app.post("/api/alerts/rules/delete")
def alert_rule_delete(inp: AlertDeleteIn):
    return engine.delete_alert_rule(inp.id)


@app.get("/api/alerts/evaluate")
def alert_evaluate():
    return engine.evaluate_alerts()


@app.post("/api/alerts/backtest")
def alert_backtest(inp: AlertBacktestIn):
    return engine.backtest_rule(inp.rule, inp.symbol)


@app.get("/api/edge/{symbol:path}")
def edge_signals(symbol: str):
    return engine.edge_signals(symbol)


@app.get("/api/regime")
def regime():
    return engine.regime_view()


@app.get("/api/signals/ideas")
def signal_ideas():
    return engine.signal_ideas()


@app.get("/api/signals/track-record")
def signal_track_record():
    return engine.signal_track_record()


@app.get("/api/signals/study/{symbol:path}")
def signal_study(symbol: str, kind: str = "insider_buy"):
    # Declared before the catch-all /api/signals/{symbol} so it isn't shadowed.
    return engine.signal_study(symbol, kind)


@app.get("/api/signals/{symbol:path}")
def signals(symbol: str):
    return engine.signals_view(symbol)


@app.get("/api/shadow")
def shadow_review():
    return engine.shadow_review()


@app.post("/api/shadow/upload")
def shadow_upload(inp: ShadowUploadIn):
    return engine.shadow_review(inp.csv)


@app.get("/api/coach")
def coach():
    return engine.coach()


@app.get("/api/mandate")
def get_mandate():
    return engine.live_status()


@app.post("/api/mandate")
def set_mandate(inp: MandateIn):
    patch = {k: v for k, v in inp.model_dump().items() if v is not None}
    engine.set_mandate(patch)
    return engine.live_status()


@app.post("/api/halt")
def set_halt(inp: HaltIn):
    return engine.set_halt(inp.on)


# ---- serve the built frontend (web/dist) ----
if (WEB_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST / "assets")), name="assets")


@app.get("/")
def index():
    idx = WEB_DIST / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return {"message": "Frontend not built yet. Run: cd web && npm run build"}


@app.get("/{path:path}")
def spa(path: str):
    if path.startswith("api/"):
        return {"error": "not found"}
    target = WEB_DIST / path
    if target.exists() and target.is_file():
        return FileResponse(str(target))
    idx = WEB_DIST / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return {"error": "frontend not built"}
