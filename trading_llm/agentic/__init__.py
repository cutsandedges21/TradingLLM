"""Phase 8 — agent-native layer: tools, an LLM tool-calling loop, and an MCP server.

- ``tools.build_registry(engine)`` wraps the app's capabilities as callable tools.
- ``loop.AgentLoop`` lets the in-app LLM decide which tools to call (agent mode).
- ``mcp_server`` exposes the same tools to external agents (Claude Desktop, etc.):
      python -m trading_llm.agentic.mcp_server
"""
from trading_llm.agentic.tools import build_registry, ToolRegistry, Tool
from trading_llm.agentic.loop import AgentLoop

__all__ = ["build_registry", "ToolRegistry", "Tool", "AgentLoop"]
