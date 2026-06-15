"""Provider transport clients (ported from the original ``llm/`` package).

Each client guards its third-party import so that merely importing the brain
layer never hard-fails when an optional provider lib is absent; an unconfigured
provider simply reports itself unavailable and the router falls through.
"""

from trading_llm.brain.clients.gemini_client import GeminiClient
from trading_llm.brain.clients.openrouter_client import OpenRouterClient
from trading_llm.brain.clients.ollama_client import OllamaClient

__all__ = ["GeminiClient", "OpenRouterClient", "OllamaClient"]
