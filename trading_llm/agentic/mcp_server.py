"""MCP server — exposes Trading LLM's capabilities to any MCP client.

Run it and point Claude Desktop / Cursor / any MCP-aware agent at it:

    python -m trading_llm.agentic.mcp_server      # stdio transport

The agent then gets tools: get_quote, market_snapshot, account_summary,
run_backtest, optimize_strategy, scan_factors, review_trades, trading_scorecard,
list_skills, read_skill — backed by the same engine the web app uses. Ported in
spirit from Vibe-Trading's ``vibe-trading-mcp``.
"""
from __future__ import annotations

import json
from functools import lru_cache

try:
    from mcp.server.fastmcp import FastMCP
    _MCP_OK = True
except Exception:  # pragma: no cover - optional dep
    FastMCP = None  # type: ignore
    _MCP_OK = False


@lru_cache(maxsize=1)
def _engine():
    from trading_llm.core.engine import TradingEngine
    return TradingEngine()


def _json(obj) -> str:
    return obj if isinstance(obj, str) else json.dumps(obj, default=str)


def build_server():
    """Create the FastMCP server with all tools registered."""
    if not _MCP_OK:
        raise RuntimeError("The 'mcp' package is not installed. Run: pip install mcp")

    mcp = FastMCP("Trading LLM")

    @mcp.tool()
    def get_quote(symbol: str) -> str:
        """Latest price and day change for a ticker (e.g. AAPL, BTC/USD)."""
        return _json(_engine().quotes([symbol.upper()]))

    @mcp.tool()
    def market_snapshot() -> str:
        """Live price + RSI/SMA/MACD/trend for the configured watchlist."""
        return _json(_engine().watchlist_rows())

    @mcp.tool()
    def account_summary() -> str:
        """The paper account: equity, cash, P&L, and open positions."""
        e = _engine()
        return _json({"account": e.account(), "positions": e.positions()})

    @mcp.tool()
    def run_backtest(symbol: str, strategy: str = "sma_cross", period: str = "2y") -> str:
        """Backtest a built-in strategy (sma_cross, ema_cross, rsi_reversion, macd,
        price_above_sma, buy_hold) on a symbol; returns metrics + a plain-English brief."""
        return _engine().backtest_spec({"symbol": symbol, "strategy": strategy, "period": period})["explanation"]

    @mcp.tool()
    def optimize_strategy(symbol: str, strategy: str = "sma_cross",
                          period: str = "2y", metric: str = "sharpe") -> str:
        """Sweep a strategy's parameters to find the best by a metric (with overfitting caveat)."""
        return _engine().optimize_spec(
            {"symbol": symbol, "strategy": strategy, "period": period, "metric": metric})["explanation"]

    @mcp.tool()
    def scan_factors(period: str = "2y", horizon: int = 5) -> str:
        """Rank a zoo of quant alpha factors by IC/IR over a liquid large-cap universe."""
        return _engine().factor_bench({"period": period, "horizon": horizon})["explanation"]

    @mcp.tool()
    def review_trades() -> str:
        """Behavior review of the paper-trade journal: biases + a plain-English report."""
        return _engine().shadow_review()["reply"]

    @mcp.tool()
    def trading_scorecard() -> str:
        """A discipline grade + challenges for the paper account."""
        return _engine().coach()["reply"]

    @mcp.tool()
    def list_skills() -> str:
        """List the finance knowledge topics in the local library."""
        return _json(_engine().list_skills())

    @mcp.tool()
    def read_skill(name: str) -> str:
        """Read a finance knowledge topic by name (e.g. rsi, risk-management)."""
        return _json(_engine().get_skill(name) or {"error": "not found"})

    @mcp.tool()
    def remember_note(text: str) -> str:
        """Save a durable free-form note to the user's persistent memory."""
        from trading_llm.memory import notes
        return _json(notes.add(text))

    @mcp.tool()
    def recall_notes(query: str) -> str:
        """Search the user's saved notes by keyword."""
        from trading_llm.memory import notes
        return _json(notes.search(query, 8))

    @mcp.tool()
    def set_goal(title: str) -> str:
        """Create a persistent research goal."""
        from trading_llm.memory import goals
        return _json(goals.add(title))

    @mcp.tool()
    def list_goals() -> str:
        """List active research goals."""
        from trading_llm.memory import goals
        return _json(goals.active())

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
