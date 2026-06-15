"""Tool registry — wraps the app's capabilities as callable tools.

The same tools power two consumers: the in-app agentic loop (the LLM decides which
to call) and the MCP server (external agents like Claude Desktop call them). Each
tool wraps a ``TradingEngine`` method and returns a string (JSON or markdown).
Pattern ported from Vibe-Trading's BaseTool/ToolRegistry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from trading_llm.backtest import list_strategies


def _strategy_names() -> list[str]:
    return [s["name"] for s in list_strategies()]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON Schema for the arguments
    fn: Callable[..., Any]     # returns a JSON-serializable object or str

    def execute(self, **kwargs) -> str:
        try:
            out = self.fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc)})
        if isinstance(out, str):
            return out
        return json.dumps(out, default=str)

    def openai_schema(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.parameters or {"type": "object", "properties": {}}}}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def openai_schemas(self) -> list[dict]:
        return [t.openai_schema() for t in self._tools.values()]

    def definitions(self) -> list[dict]:
        return [{"name": t.name, "description": t.description, "parameters": t.parameters}
                for t in self._tools.values()]

    def execute(self, name: str, args: dict | None = None) -> str:
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Unknown tool '{name}'"})
        return tool.execute(**(args or {}))

    def __len__(self) -> int:
        return len(self._tools)


def build_registry(engine) -> ToolRegistry:
    """Build the standard tool set bound to a TradingEngine."""
    r = ToolRegistry()
    strat_enum = _strategy_names()

    r.register(Tool(
        "get_quote", "Get the latest price and day change for one ticker (e.g. AAPL, BTC/USD).",
        {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
        lambda symbol: engine.quotes([symbol.upper()])))

    r.register(Tool(
        "market_snapshot", "Live price + RSI/SMA/MACD/trend for the watchlist (or given symbols).",
        {"type": "object", "properties": {"symbols": {"type": "array", "items": {"type": "string"}}}},
        lambda symbols=None: engine.watchlist_rows() if not symbols
        else engine.quotes([s.upper() for s in symbols])))

    r.register(Tool(
        "account_summary", "The paper account: equity, cash, P&L, and open positions.",
        {"type": "object", "properties": {}},
        lambda: {"account": engine.account(), "positions": engine.positions()}))

    r.register(Tool(
        "run_backtest", "Backtest a built-in strategy on a symbol; returns metrics + a plain-English brief.",
        {"type": "object", "properties": {
            "symbol": {"type": "string"},
            "strategy": {"type": "string", "enum": strat_enum},
            "period": {"type": "string", "enum": ["6mo", "1y", "2y", "5y"]}},
         "required": ["symbol"]},
        lambda symbol, strategy="sma_cross", period="2y":
            engine.backtest_spec({"symbol": symbol, "strategy": strategy, "period": period})["explanation"]))

    r.register(Tool(
        "optimize_strategy", "Sweep a strategy's parameters to find the best by a metric (with overfitting caveat).",
        {"type": "object", "properties": {
            "symbol": {"type": "string"},
            "strategy": {"type": "string", "enum": strat_enum},
            "period": {"type": "string"}, "metric": {"type": "string", "enum": ["sharpe", "total_return_pct", "cagr_pct"]}},
         "required": ["symbol"]},
        lambda symbol, strategy="sma_cross", period="2y", metric="sharpe":
            engine.optimize_spec({"symbol": symbol, "strategy": strategy, "period": period, "metric": metric})["explanation"]))

    r.register(Tool(
        "scan_factors", "Rank a zoo of quant alpha factors by IC/IR over a liquid universe.",
        {"type": "object", "properties": {
            "period": {"type": "string"}, "horizon": {"type": "integer"}}},
        lambda period="2y", horizon=5:
            engine.factor_bench({"period": period, "horizon": horizon})["explanation"]))

    r.register(Tool(
        "review_trades", "Behavior review of the paper-trade journal: biases + a plain-English report.",
        {"type": "object", "properties": {}},
        lambda: engine.shadow_review()["reply"]))

    r.register(Tool(
        "trading_scorecard", "A discipline grade + challenges for the paper account.",
        {"type": "object", "properties": {}},
        lambda: engine.coach()["reply"]))

    r.register(Tool(
        "list_skills", "List the finance knowledge topics in the local library.",
        {"type": "object", "properties": {}},
        lambda: engine.list_skills()))

    r.register(Tool(
        "read_skill", "Read a finance knowledge topic by name (e.g. rsi, risk-management).",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        lambda name: engine.get_skill(name) or {"error": "not found"}))

    # persistent memory + research goals (Phase 10)
    from trading_llm.memory import notes as notes_mem, goals as goals_mem

    r.register(Tool(
        "remember_note", "Save a durable free-form note to memory for later recall.",
        {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        lambda text: notes_mem.add(text)))

    r.register(Tool(
        "recall_notes", "Search saved notes by keyword.",
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        lambda query: notes_mem.search(query, 8)))

    r.register(Tool(
        "set_goal", "Create a persistent research goal the copilot will track.",
        {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
        lambda title: goals_mem.add(title)))

    r.register(Tool(
        "list_goals", "List active research goals.",
        {"type": "object", "properties": {}},
        lambda: goals_mem.active()))

    return r
