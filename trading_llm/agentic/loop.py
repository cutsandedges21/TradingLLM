"""Agentic tool-calling loop — the LLM decides which tools to call.

Binds the ToolRegistry to a LangChain chat model (from ``ProviderRouter.get_llm``),
then iterates: the model requests tool calls, we execute them and feed results back,
until it produces a final answer. This is the agent-native upgrade over keyword
routing; the engine falls back to keyword routing when no LangChain provider exists.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _content(resp) -> str:
    c = getattr(resp, "content", None)
    if isinstance(c, list):
        c = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return (c if isinstance(c, str) else str(resp)).strip()


def _tc_field(tc, key: str, default=None):
    return tc.get(key, default) if isinstance(tc, dict) else getattr(tc, key, default)


class AgentLoop:
    def __init__(self, router, registry, max_iters: int = 5):
        self.router = router
        self.registry = registry
        self.max_iters = max_iters
        self._ok: bool | None = None

    def available(self) -> bool:
        if self._ok is None:
            try:
                self.router.get_llm("quick")
                self._ok = True
            except Exception:
                self._ok = False
        return self._ok

    def run(self, user_text: str, system_prompt: str) -> dict:
        from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

        llm = self.router.get_llm("quick")
        bound = llm.bind_tools(self.registry.openai_schemas()) if hasattr(llm, "bind_tools") else llm
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_text)]
        used: list[str] = []

        for _ in range(self.max_iters):
            resp = bound.invoke(messages)
            tool_calls = getattr(resp, "tool_calls", None) or []
            if not tool_calls:
                return {"reply": _content(resp), "tools_used": used}
            messages.append(resp)
            for tc in tool_calls:
                name = _tc_field(tc, "name")
                args = _tc_field(tc, "args", {}) or {}
                cid = _tc_field(tc, "id") or name
                result = self.registry.execute(name, args)
                used.append(name)
                messages.append(ToolMessage(content=str(result)[:6000], tool_call_id=cid))

        # ran out of iterations — ask once more for a final synthesis
        return {"reply": _content(bound.invoke(messages)), "tools_used": used}
