"""Alert rule model + evaluation — the automation layer.

A rule is a set of AND-conditions over per-symbol features. Each field is tagged
``pit`` (point-in-time): price-computable fields can be honestly walk-forward
backtested; smart-money fields (composite, insider, 13F, regime) have no
point-in-time history, so they're live/forward-only. Evaluation is pure + tested.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# field -> metadata. pit=True means it can be reconstructed historically from price.
FIELDS: dict[str, dict] = {
    "rsi": {"label": "RSI(14)", "type": "num", "pit": True},
    "trend": {"label": "Trend", "type": "cat", "pit": True, "choices": ["up", "down", "sideways"]},
    "price_vs_sma200_pct": {"label": "% vs 200-day SMA", "type": "num", "pit": True},
    "macd": {"label": "MACD", "type": "cat", "pit": True, "choices": ["bullish", "bearish", "flat"]},
    "seasonality_month_pct": {"label": "Seasonality (this month %)", "type": "num", "pit": True},
    "composite": {"label": "Composite score", "type": "num", "pit": False},
    "insider_buys_30d": {"label": "Insider buys (30d)", "type": "num", "pit": False},
    "net_insider_30d": {"label": "Net insider $ (30d)", "type": "num", "pit": False},
    "funds_holding": {"label": "Tracked funds holding", "type": "num", "pit": False},
    "regime": {"label": "Market regime", "type": "cat", "pit": False,
               "choices": ["risk_on", "neutral", "risk_off"]},
    "squeeze_score": {"label": "Squeeze score", "type": "num", "pit": False},
}
OPS = (">=", "<=", ">", "<", "==")


def _cmp(val, op: str, target) -> bool:
    if op == "==":
        return str(val).strip().lower() == str(target).strip().lower()
    try:
        v, t = float(val), float(target)
    except (TypeError, ValueError):
        return False
    return {">=": v >= t, "<=": v <= t, ">": v > t, "<": v < t}.get(op, False)


def evaluate_condition(cond: dict, features: dict) -> bool:
    field_name = cond.get("field")
    if field_name not in FIELDS:
        return False
    val = features.get(field_name)
    if val is None:
        return False
    return _cmp(val, cond.get("op", ">="), cond.get("value"))


def evaluate_conditions(conditions: list[dict], features: dict) -> bool:
    """True only if EVERY condition holds (AND). Empty rule never fires."""
    return bool(conditions) and all(evaluate_condition(c, features) for c in conditions)


def matched_conditions(conditions: list[dict], features: dict) -> list[dict]:
    """Per-condition pass/fail + the actual value seen — for explainability."""
    out = []
    for c in conditions:
        out.append({**c, "value_seen": features.get(c.get("field")),
                    "pass": evaluate_condition(c, features)})
    return out


def is_backtestable(rule: dict) -> tuple[bool, list[str]]:
    """A rule is walk-forward backtestable only if all its conditions are point-in-time.
    Returns (ok, forward_only_fields)."""
    forward = [c["field"] for c in rule.get("conditions", [])
               if FIELDS.get(c.get("field"), {}).get("pit") is False]
    return (len(forward) == 0, forward)


@dataclass
class Rule:
    id: str
    name: str
    conditions: list[dict] = field(default_factory=list)
    scope: str = "universe"          # "universe" or "symbols"
    symbols: list[str] = field(default_factory=list)
    action: str = "buy"
    hold_days: int = 20
    risk_pct: float = 0.01
    enabled: bool = True
    created: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @staticmethod
    def from_dict(d: dict) -> "Rule":
        return Rule(
            id=str(d.get("id", "")), name=str(d.get("name", "Rule")),
            conditions=list(d.get("conditions", [])), scope=d.get("scope", "universe"),
            symbols=[s.upper() for s in d.get("symbols", [])], action=d.get("action", "buy"),
            hold_days=int(d.get("hold_days", 20)), risk_pct=float(d.get("risk_pct", 0.01)),
            enabled=bool(d.get("enabled", True)), created=str(d.get("created", "")),
        )
