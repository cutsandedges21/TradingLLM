"""Unified provider router — the single brain seam for the whole app.

Two responsibilities:

1. ``chat()`` / ``chat_json()`` — the proven Phase-0 path. Routes across
   Gemini -> OpenRouter -> Ollama with multi-key / multi-model fallback,
   exactly as the original ``Brain`` did. No LangChain required.

2. ``get_llm(kind="deep"|"quick")`` — returns a **LangChain** chat model for the
   first configured provider in the order. This is the seam the Phase-1
   multi-agent debate (TradingAgents) and Phase-2 agentic tools consume.
   LangChain is an **optional** dependency: ``get_llm`` raises a clear,
   actionable error if the needed ``langchain-*`` package is missing, but the
   rest of the app keeps working without it.

Drop-in for the original ``llm.brain.Brain``: same ``chat``, ``chat_json``,
``providers_status``, and mutable ``order`` attribute.
"""
from __future__ import annotations

import json
import re

from trading_llm.core.config import gemini_keys, openrouter_keys
from trading_llm.brain.clients import GeminiClient, OpenRouterClient, OllamaClient


class ProviderRouter:
    def __init__(self, settings: dict, keys: dict):
        llm = settings["llm"]
        self.order = list(llm.get("provider_order", ["gemini", "openrouter", "ollama"]))
        self.temperature = llm.get("temperature", 0.4)
        self.max_tokens = llm.get("max_tokens", 2048)

        # Keep raw config around for get_llm() (LangChain model construction).
        self._llm_cfg = llm
        self._gemini_keys = gemini_keys(keys)
        self._openrouter_keys = openrouter_keys(keys)

        self.gemini = GeminiClient(self._gemini_keys, llm["gemini_model"], llm["gemini_deep_model"])
        self.openrouter = OpenRouterClient(self._openrouter_keys, llm.get("openrouter_models", []))
        self.ollama = OllamaClient(llm.get("ollama_model", "llama3.1:8b"))

    # ---------- status ----------
    def providers_status(self) -> dict:
        return {
            "gemini": self.gemini.available,
            "openrouter": self.openrouter.available,
            "ollama": "checked on use",
        }

    # ---------- chat (Phase 0 path) ----------
    def chat(self, system: str, messages: list[dict], deep: bool = False) -> tuple[str, str]:
        errors = []
        for name in self.order:
            try:
                if name == "gemini" and self.gemini.available:
                    text = self.gemini.chat(system, messages, deep=deep,
                                            temperature=self.temperature, max_tokens=self.max_tokens)
                    return text, ("gemini-pro" if deep else "gemini")
                if name == "openrouter" and self.openrouter.available:
                    text = self.openrouter.chat(system, messages,
                                                temperature=self.temperature, max_tokens=self.max_tokens)
                    return text, "openrouter"
                if name == "ollama" and self.ollama.available():
                    text = self.ollama.chat(system, messages,
                                            temperature=self.temperature, max_tokens=self.max_tokens)
                    return text, "ollama (local)"
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        raise RuntimeError(
            "No LLM provider could answer.\n" + "\n".join(errors)
            + "\n\nCheck your keys in config/api_keys.json, or start Ollama "
              "(`ollama serve` + `ollama pull llama3.1:8b`) for offline use."
        )

    def chat_json(self, system: str, prompt: str) -> dict:
        """Single-shot prompt expected to return JSON (used for memory extraction)."""
        try:
            raw, _ = self.chat(system, [{"role": "user", "content": prompt}])
        except Exception:
            return {}
        clean = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
        if not clean or clean == "{}":
            return {}
        try:
            data = json.loads(clean)
            return data if isinstance(data, dict) else {}
        except Exception:
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    return {}
            return {}

    # ---------- LangChain seam (Phase 1+) ----------
    def first_available_provider(self) -> str | None:
        """First provider in the order that is configured enough to build an LLM."""
        for name in self.order:
            if name == "gemini" and self._gemini_keys:
                return "gemini"
            if name == "openrouter" and self._openrouter_keys and self._llm_cfg.get("openrouter_models"):
                return "openrouter"
            if name == "ollama":
                return "ollama"  # local; assume reachable, validated on use
        return None

    def get_llm(self, kind: str = "quick", provider: str | None = None):
        """Return a LangChain chat model for the chosen/first-available provider.

        ``kind`` is "deep" (slower, stronger model) or "quick" (faster model).
        Raises a clear, actionable error when the relevant ``langchain-*``
        package is not installed — Phase 0 never calls this; Phase 1 does.
        """
        provider = provider or self.first_available_provider()
        if provider is None:
            raise RuntimeError(
                "No LLM provider is configured. Add keys to config/api_keys.json "
                "or run Ollama locally."
            )
        cfg = self._llm_cfg
        temperature = self.temperature

        if provider == "gemini":
            model = cfg["gemini_deep_model"] if kind == "deep" else cfg["gemini_model"]
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except Exception as exc:  # pragma: no cover - optional dep
                raise RuntimeError(
                    "get_llm(gemini) needs the 'langchain-google-genai' package "
                    "(pip install langchain-google-genai). " + str(exc)
                )
            key = self._gemini_keys[0] if self._gemini_keys else None
            return ChatGoogleGenerativeAI(model=model, google_api_key=key, temperature=temperature)

        if provider == "openrouter":
            models = cfg.get("openrouter_models", [])
            model = models[0] if models else "openrouter/auto"
            try:
                from langchain_openai import ChatOpenAI
            except Exception as exc:  # pragma: no cover - optional dep
                raise RuntimeError(
                    "get_llm(openrouter) needs the 'langchain-openai' package "
                    "(pip install langchain-openai). " + str(exc)
                )
            key = self._openrouter_keys[0] if self._openrouter_keys else None
            return ChatOpenAI(model=model, api_key=key,
                              base_url="https://openrouter.ai/api/v1", temperature=temperature)

        if provider == "ollama":
            model = cfg.get("ollama_model", "llama3.1:8b")
            try:
                from langchain_ollama import ChatOllama
            except Exception as exc:  # pragma: no cover - optional dep
                raise RuntimeError(
                    "get_llm(ollama) needs the 'langchain-ollama' package "
                    "(pip install langchain-ollama). " + str(exc)
                )
            return ChatOllama(model=model, temperature=temperature)

        raise RuntimeError(f"Unknown provider: {provider}")


# Backwards-friendly alias: the engine and tests can import either name.
Brain = ProviderRouter
