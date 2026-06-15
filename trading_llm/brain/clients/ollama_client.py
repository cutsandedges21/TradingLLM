"""Local Ollama client (offline / privacy fallback).

Used only when reached in the provider order (normally after the cloud brains).
Requires `ollama serve` to be running and at least one model pulled, e.g.:
    ollama pull llama3.1:8b
"""
from __future__ import annotations

try:
    import ollama
    _OLLAMA_OK = True
except Exception:  # pragma: no cover
    ollama = None  # type: ignore
    _OLLAMA_OK = False


def _model_names(list_resp) -> list[str]:
    models = getattr(list_resp, "models", None)
    if models is None and isinstance(list_resp, dict):
        models = list_resp.get("models", [])
    names = []
    for m in models or []:
        name = getattr(m, "model", None) or (m.get("model") or m.get("name") if isinstance(m, dict) else None)
        if name:
            names.append(name)
    return names


class OllamaClient:
    def __init__(self, model: str):
        self.model = model

    def available(self) -> bool:
        if not _OLLAMA_OK:
            return False
        try:
            ollama.list()
            return True
        except Exception:
            return False

    def _pick_model(self) -> str:
        try:
            names = _model_names(ollama.list())
            if self.model in names:
                return self.model
            return names[0] if names else self.model
        except Exception:
            return self.model

    def chat(self, system: str, messages: list[dict],
             temperature: float = 0.4, max_tokens: int = 2048) -> str:
        if not _OLLAMA_OK:
            raise RuntimeError("ollama is not installed.")
        msgs = [{"role": "system", "content": system}]
        for m in messages:
            role = "assistant" if m.get("role") in ("assistant", "model") else "user"
            msgs.append({"role": role, "content": str(m.get("content", ""))})

        resp = ollama.chat(
            model=self._pick_model(),
            messages=msgs,
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        msg = resp.get("message") if isinstance(resp, dict) else getattr(resp, "message", None)
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
        return (content or "").strip()
