"""OpenRouter fallback client (free-tier models) with key rotation + self-healing.

Free model IDs on OpenRouter change and go stale (404). This client tries the
configured models, and if they all fail it **discovers currently-available free
models** from the live catalogue and retries — so the fallback fixes itself
instead of silently staying broken.
"""
from __future__ import annotations

try:
    import requests
    _REQUESTS_OK = True
except Exception:  # pragma: no cover
    requests = None  # type: ignore
    _REQUESTS_OK = False

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
TIMEOUT = 60


def parse_free_models(payload: dict, limit: int = 8) -> list[str]:
    """Extract ':free' model ids from an OpenRouter /models response."""
    data = payload.get("data", []) if isinstance(payload, dict) else []
    free = [str(m.get("id", "")) for m in data if str(m.get("id", "")).endswith(":free")]
    return [m for m in free if m][:limit]


class OpenRouterClient:
    def __init__(self, api_keys: list[str], models: list[str]):
        self.keys = [k for k in api_keys if k]
        self.models = models or []
        self._discovered: list[str] | None = None

    @property
    def available(self) -> bool:
        # Models can be discovered at call time, so keys alone are enough.
        return bool(self.keys) and _REQUESTS_OK

    def _headers(self, key: str) -> dict:
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost/trading-llm",
            "X-Title": "Trading LLM",
        }

    def _discover_free_models(self) -> list[str]:
        if self._discovered is not None:
            return self._discovered
        self._discovered = []
        if not (_REQUESTS_OK and self.keys):
            return self._discovered
        try:
            r = requests.get(MODELS_URL, headers=self._headers(self.keys[0]), timeout=TIMEOUT)
            if r.status_code == 200:
                self._discovered = parse_free_models(r.json())
        except Exception:
            pass
        return self._discovered

    def _try_models(self, models, payload_messages, temperature, max_tokens) -> tuple[str | None, str]:
        last_err = "no models to try"
        for key in self.keys:
            for model in models:
                try:
                    resp = requests.post(
                        API_URL, headers=self._headers(key), timeout=TIMEOUT,
                        json={"model": model, "messages": payload_messages,
                              "temperature": temperature, "max_tokens": max_tokens})
                    if resp.status_code == 200:
                        content = (resp.json().get("choices", [{}])[0]
                                   .get("message", {}).get("content", ""))
                        if content and content.strip():
                            return content.strip(), ""
                        last_err = f"{model}: empty response"
                    elif resp.status_code in (429, 402):
                        last_err = f"{model}: rate/credit limited ({resp.status_code})"
                    else:
                        last_err = f"{model}: HTTP {resp.status_code}"
                except Exception as exc:
                    last_err = f"{model}: {exc}"
        return None, last_err

    def chat(self, system: str, messages: list[dict],
             temperature: float = 0.4, max_tokens: int = 2048) -> str:
        if not _REQUESTS_OK:
            raise RuntimeError("requests is not installed.")
        if not self.keys:
            raise RuntimeError("No OpenRouter keys configured.")
        payload_messages = [{"role": "system", "content": system}]
        for m in messages:
            role = "assistant" if m.get("role") in ("assistant", "model") else "user"
            payload_messages.append({"role": role, "content": str(m.get("content", ""))})

        content, last_err = self._try_models(self.models, payload_messages, temperature, max_tokens)
        if content is not None:
            return content
        # configured models all failed (often stale 404s) — self-heal from the catalogue
        discovered = [m for m in self._discover_free_models() if m not in self.models]
        if discovered:
            content, last_err = self._try_models(discovered, payload_messages, temperature, max_tokens)
            if content is not None:
                return content
        raise RuntimeError(f"OpenRouter failed: {last_err}")
