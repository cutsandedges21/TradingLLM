"""Loads user settings and API keys, with sane defaults applied on top.

Ported from the original ``app_config.py``. The on-disk files
(``config/settings.json`` and ``config/api_keys.json``) are unchanged, so
existing installs keep working without migration.
"""
from __future__ import annotations

import os

from trading_llm.core.paths import CONFIG_DIR, load_json, save_json

DEFAULT_SETTINGS: dict = {
    "watchlist": ["SPY", "QQQ", "AAPL", "NVDA", "TSLA", "BTC/USD"],
    "default_timeframe": "1Day",
    "bars_lookback": 120,
    "data_source_order": ["finnhub", "yfinance", "alpaca"],
    "trading_mode": "mock",
    "mock_starting_cash": 100000,
    "beginner_mode": False,
    # Fill realism for the paper broker (basis points). Market orders slip against
    # you; a commission is charged on notional. Set to 0/0 for frictionless fills.
    "execution": {"slippage_bps": 2.0, "fee_bps": 1.0},
    "llm": {
        "provider_order": ["gemini", "openrouter", "ollama"],
        "gemini_model": "gemini-2.5-flash",
        "gemini_deep_model": "gemini-2.5-pro",
        "openrouter_models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "meta-llama/llama-3.1-8b-instruct:free",
        ],
        "ollama_model": "llama3.1:8b",
        "temperature": 0.4,
        "max_tokens": 2048,
    },
    "risk": {
        "max_position_usd": 2000,
        "max_trades_per_day": 10,
        "require_confirmation": True,
    },
    # Opt-in real (Alpaca PAPER) trading behind a committed mandate. OFF by default —
    # the local mock broker handles everything unless you enable this AND add Alpaca keys.
    "live_trading": {
        "enabled": False,
        "max_order_usd": 1000,
        "max_trades_per_day": 5,
        "allowed_symbols": [],
    },
    # Phase 1 multi-agent "deep analysis" debate. More rounds = deeper (and slower
    # / more LLM calls). 1 each ≈ 10 calls per deep analysis.
    "debate": {
        "research_rounds": 1,
        "risk_rounds": 1,
    },
}

DEFAULT_KEYS: dict = {
    "gemini_api_keys": [],
    "openrouter_api_keys": [],
    "finnhub_api_key": "",
    "alpaca_paper_key": "",
    "alpaca_paper_secret": "",
    "alpaca_paper": True,
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_settings() -> dict:
    return _deep_merge(DEFAULT_SETTINGS, load_json(CONFIG_DIR / "settings.json", {}))


def save_settings(settings: dict) -> None:
    save_json(CONFIG_DIR / "settings.json", settings)


def _env_list(name: str) -> list[str]:
    val = os.environ.get(name, "")
    return [k.strip() for k in val.split(",") if k.strip()]


def load_keys() -> dict:
    """Keys from config/api_keys.json, then overlaid by environment variables.

    Env vars win, so the security-conscious can keep secrets OUT of the synced file:
      GEMINI_API_KEYS / GEMINI_API_KEY, OPENROUTER_API_KEYS / OPENROUTER_API_KEY,
      FINNHUB_API_KEY, ALPACA_PAPER_KEY, ALPACA_PAPER_SECRET.
    """
    keys = _deep_merge(DEFAULT_KEYS, load_json(CONFIG_DIR / "api_keys.json", {}))

    gem = _env_list("GEMINI_API_KEYS") or _env_list("GEMINI_API_KEY")
    if gem:
        keys["gemini_api_keys"] = gem
    orouter = _env_list("OPENROUTER_API_KEYS") or _env_list("OPENROUTER_API_KEY")
    if orouter:
        keys["openrouter_api_keys"] = orouter
    if os.environ.get("FINNHUB_API_KEY"):
        keys["finnhub_api_key"] = os.environ["FINNHUB_API_KEY"].strip()
    if os.environ.get("ALPACA_PAPER_KEY"):
        keys["alpaca_paper_key"] = os.environ["ALPACA_PAPER_KEY"].strip()
    if os.environ.get("ALPACA_PAPER_SECRET"):
        keys["alpaca_paper_secret"] = os.environ["ALPACA_PAPER_SECRET"].strip()
    return keys


def api_auth_key() -> str:
    """Token required for NON-loopback API access (empty = localhost-only).

    Set via env TRADING_LLM_API_KEY or "api_auth_key" in settings.json.
    """
    env = os.environ.get("TRADING_LLM_API_KEY", "").strip()
    if env:
        return env
    val = load_settings().get("api_auth_key", "")
    return str(val).strip() if val else ""


def gemini_keys(keys: dict | None = None) -> list[str]:
    keys = keys or load_keys()
    return [k.strip() for k in keys.get("gemini_api_keys", []) if k and k.strip()]


def openrouter_keys(keys: dict | None = None) -> list[str]:
    keys = keys or load_keys()
    return [k.strip() for k in keys.get("openrouter_api_keys", []) if k and k.strip()]


def finnhub_key(keys: dict | None = None) -> str:
    keys = keys or load_keys()
    value = keys.get("finnhub_api_key", "")
    return value.strip() if isinstance(value, str) else ""
