"""Gemini text client (primary 'smart' brain) with multi-key rotation.

Rotating across your keys roughly multiplies the free-tier headroom: on any
error (rate limit, quota, transient), we advance to the next key and retry.

The ``google-genai`` import is guarded so importing the brain layer never fails
when the lib is absent — an unconfigured/unimportable client just reports
``available == False``.
"""
from __future__ import annotations

try:
    from google import genai
    from google.genai import types
    _GENAI_OK = True
except Exception:  # pragma: no cover - optional at import time
    genai = None  # type: ignore
    types = None  # type: ignore
    _GENAI_OK = False


def _part(text: str):
    # Works across google-genai point releases.
    try:
        return types.Part.from_text(text=text)
    except Exception:  # pragma: no cover
        return types.Part(text=text)


class GeminiClient:
    def __init__(self, api_keys: list[str], model: str, deep_model: str):
        self.keys = [k for k in api_keys if k]
        self.model = model
        self.deep_model = deep_model
        self._idx = 0

    @property
    def available(self) -> bool:
        return bool(self.keys) and _GENAI_OK

    def _to_contents(self, messages: list[dict]):
        contents = []
        for m in messages:
            role = "model" if m.get("role") in ("assistant", "model") else "user"
            contents.append(types.Content(role=role, parts=[_part(str(m.get("content", "")))]))
        return contents

    def chat(self, system: str, messages: list[dict], deep: bool = False,
             temperature: float = 0.4, max_tokens: int = 2048) -> str:
        if not _GENAI_OK:
            raise RuntimeError("google-genai is not installed.")
        if not self.keys:
            raise RuntimeError("No Gemini keys configured.")
        model = self.deep_model if deep else self.model
        contents = self._to_contents(messages)
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        last_err = "unknown error"
        for _ in range(len(self.keys)):
            key = self.keys[self._idx % len(self.keys)]
            try:
                client = genai.Client(api_key=key)
                resp = client.models.generate_content(model=model, contents=contents, config=cfg)
                text = (resp.text or "").strip()
                if text:
                    return text
                last_err = "empty response (possibly safety-blocked)"
            except Exception as exc:
                last_err = str(exc)
            finally:
                self._idx += 1  # always rotate so load spreads across keys
        raise RuntimeError(f"Gemini failed across {len(self.keys)} key(s): {last_err}")
