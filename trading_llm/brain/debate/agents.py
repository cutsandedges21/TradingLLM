"""Individual agent roles — each is one LangChain LLM call over our context.

Kept thin and side-effect-free so the pipeline (and tests) can compose them
freely. Every function returns plain text.
"""
from __future__ import annotations

import time

from trading_llm.brain.debate import prompts

# Substrings that mark a transient provider error worth one retry.
_TRANSIENT = ("429", "resource_exhausted", "rate", "503", "unavailable", "overloaded", "timeout")


def _text(resp) -> str:
    """Extract text from a LangChain AIMessage (or anything stringable)."""
    content = getattr(resp, "content", None)
    if content is None:
        return str(resp).strip()
    if isinstance(content, list):  # some providers return content parts
        content = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content).strip()


def _invoke(llm, prompt, retries: int = 1, backoff: float = 8.0) -> str:
    """Invoke a LangChain model with one backoff retry on transient (rate/availability) errors."""
    last = None
    for attempt in range(retries + 1):
        try:
            return _text(llm.invoke(prompt))
        except Exception as exc:  # noqa: BLE001 - provider exceptions vary
            last = exc
            if attempt < retries and any(k in str(exc).lower() for k in _TRANSIENT):
                time.sleep(backoff)
                continue
            raise
    raise last  # unreachable, keeps type-checkers happy


# ---- analysts ----
def run_market_analyst(llm, ticker: str, technical_context: str) -> str:
    return _invoke(llm, prompts.market_analyst_prompt(ticker, technical_context))


def run_news_analyst(llm, ticker: str, news_context: str) -> str:
    return _invoke(llm, prompts.news_analyst_prompt(ticker, news_context))


def run_smart_money_analyst(llm, ticker: str, signals_context: str) -> str:
    return _invoke(llm, prompts.smart_money_analyst_prompt(ticker, signals_context))


# ---- research debate ----
def run_bull(llm, ticker, market_report, news_report, history, last_bear, smart_money_report="") -> str:
    return _invoke(llm, prompts.bull_prompt(ticker, market_report, news_report, history,
                                            last_bear, smart_money_report))


def run_bear(llm, ticker, market_report, news_report, history, last_bull, smart_money_report="") -> str:
    return _invoke(llm, prompts.bear_prompt(ticker, market_report, news_report, history,
                                            last_bull, smart_money_report))


def run_research_manager(llm, ticker, history) -> str:
    return _invoke(llm, prompts.research_manager_prompt(ticker, history))


# ---- trader ----
def run_trader(llm, ticker, investment_plan) -> str:
    messages = [
        ("system", prompts.trader_system_prompt()),
        ("human", prompts.trader_user_prompt(ticker, investment_plan)),
    ]
    return _invoke(llm, messages)


# ---- risk committee ----
def run_aggressive(llm, market_report, news_report, trader_decision,
                   history, last_conservative, last_neutral) -> str:
    return _invoke(llm, prompts.aggressive_prompt(
        market_report, news_report, trader_decision, history, last_conservative, last_neutral))


def run_conservative(llm, market_report, news_report, trader_decision,
                     history, last_aggressive, last_neutral) -> str:
    return _invoke(llm, prompts.conservative_prompt(
        market_report, news_report, trader_decision, history, last_aggressive, last_neutral))


def run_neutral(llm, market_report, news_report, trader_decision,
                history, last_aggressive, last_conservative) -> str:
    return _invoke(llm, prompts.neutral_prompt(
        market_report, news_report, trader_decision, history, last_aggressive, last_conservative))


# ---- portfolio manager ----
def run_portfolio_manager(llm, ticker, research_plan, trader_plan,
                          risk_history, past_context, smart_money_report="") -> str:
    return _invoke(llm, prompts.portfolio_manager_prompt(
        ticker, research_plan, trader_plan, risk_history, past_context, smart_money_report))
