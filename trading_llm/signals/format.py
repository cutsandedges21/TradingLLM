"""Rendering helpers: compact lines for the LLM snapshot + JSON dicts for the API/UI.

Kept separate from the data types so the wording can change without touching
``models.py``. The snapshot lines are deliberately terse to protect the LLM
context budget.
"""
from __future__ import annotations

from trading_llm.signals.models import Regime, SignalBundle


def _usd(n: float) -> str:
    a = abs(n)
    if a >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if a >= 1_000:
        return f"${n/1_000:.0f}K"
    return f"${n:.0f}"


def regime_summary(regime: Regime) -> str:
    """One-line regime tag for the snapshot, e.g. 'Regime: RISK-ON — trend up …'."""
    if not regime or not regime.ok:
        return ""
    return f"Regime: {regime.summary}"


def signals_summary(bundle: SignalBundle) -> str:
    """Compact per-symbol smart-money tag, or '' when there's nothing to say."""
    if not bundle or not bundle.has_data():
        return ""
    parts: list[str] = []
    net30 = bundle.net_insider_usd_30d
    if bundle.insider_buys_30d or bundle.insider_sells_30d:
        sign = "+" if net30 >= 0 else "-"
        parts.append(f"insiders {sign}{_usd(abs(net30))} "
                     f"({bundle.insider_buys_30d} buys/{bundle.insider_sells_30d} sells, 30d)")
    if bundle.funds_holding:
        parts.append(f"held by {bundle.funds_holding} tracked fund"
                     f"{'s' if bundle.funds_holding != 1 else ''}")
    if bundle.congress_trades_90d:
        parts.append(f"{bundle.congress_trades_90d} congress trade"
                     f"{'s' if bundle.congress_trades_90d != 1 else ''}/90d")
    if not parts:
        return ""
    tag = " · ".join(parts)
    if bundle.stale:
        tag += " (cached)"
    return tag


def regime_to_dict(regime: Regime) -> dict:
    return regime.to_dict()


def bundle_to_dict(bundle: SignalBundle) -> dict:
    return bundle.to_dict()
