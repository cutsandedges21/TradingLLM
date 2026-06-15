"""A safe rule DSL for custom strategies — no executing LLM-written code.

A strategy is structured data: entry/exit condition groups over indicators and
price. The LLM only ever produces this JSON; a deterministic compiler turns it
into a long/flat signal. Operands: rsi(n), sma(n), ema(n), macd_hist, and the
price columns close/open/high/low/volume, or a number. Operators: < > <= >= ==,
crosses_above, crosses_below. Groups combine conditions with "all" or "any".

Example spec:
    {"name": "RSI dip in uptrend",
     "entry": {"all": [{"left": "rsi(14)", "op": "<", "right": 35},
                       {"left": "close", "op": ">", "right": "sma(100)"}]},
     "exit":  {"any": [{"left": "rsi(14)", "op": ">", "right": 60}]}}
"""
from __future__ import annotations

import re

import pandas as pd

from trading_llm.market import indicators

_COLS = {"close", "open", "high", "low", "volume"}
_OPS = {"<", ">", "<=", ">=", "==", "crosses_above", "crosses_below"}
_IND_RE = re.compile(r"^([a-z_]+)\((\d+)\)$")


def operand_series(token, df: pd.DataFrame) -> pd.Series:
    """Resolve an operand string/number to a Series aligned to ``df``."""
    t = str(token).strip().lower()
    try:
        return pd.Series(float(t), index=df.index)  # numeric constant
    except ValueError:
        pass
    m = _IND_RE.match(t)
    if m:
        fn, n = m.group(1), int(m.group(2))
        close = df["close"]
        if fn == "rsi":
            return indicators.rsi(close, n)
        if fn == "sma":
            return indicators.sma(close, n)
        if fn == "ema":
            return indicators.ema(close, n)
        raise ValueError(f"unknown indicator: {fn}")
    if t in ("macd_hist", "macd"):
        _, _, hist = indicators.macd(df["close"])
        return hist
    if t in _COLS:
        return df[t]
    raise ValueError(f"unknown operand: {token!r}")


def _eval_condition(cond: dict, df: pd.DataFrame) -> pd.Series:
    left = operand_series(cond["left"], df)
    right = operand_series(cond["right"], df)
    op = cond["op"]
    if op == "<":
        out = left < right
    elif op == ">":
        out = left > right
    elif op == "<=":
        out = left <= right
    elif op == ">=":
        out = left >= right
    elif op == "==":
        out = (left - right).abs() < 1e-9
    elif op == "crosses_above":
        out = (left > right) & (left.shift(1) <= right.shift(1))
    elif op == "crosses_below":
        out = (left < right) & (left.shift(1) >= right.shift(1))
    else:
        raise ValueError(f"unknown operator: {op}")
    return out.fillna(False)


def _eval_group(group: dict, df: pd.DataFrame) -> pd.Series:
    if "all" in group:
        items, reducer = group["all"], True
    elif "any" in group:
        items, reducer = group["any"], False
    else:
        raise ValueError("condition group must have 'all' or 'any'")
    series = [(_eval_group(it, df) if ("all" in it or "any" in it) else _eval_condition(it, df))
              for it in items]
    if not series:
        return pd.Series(False, index=df.index)
    acc = series[0]
    for s in series[1:]:
        acc = (acc & s) if reducer else (acc | s)
    return acc


def validate(spec: dict) -> tuple[bool, str]:
    """Structural + operand validation against a small dummy frame."""
    if not isinstance(spec, dict) or "entry" not in spec or "exit" not in spec:
        return False, "Strategy must have 'entry' and 'exit' condition groups."
    dummy = pd.DataFrame({c: [float(i + 1) for i in range(30)] for c in _COLS})
    try:
        _eval_group(spec["entry"], dummy)
        _eval_group(spec["exit"], dummy)
    except Exception as exc:  # noqa: BLE001
        return False, f"Invalid rule: {exc}"
    return True, ""


def compile_signal(spec: dict, df: pd.DataFrame) -> pd.Series:
    """Compile the spec to a long/flat (0/1) signal over ``df`` (stateful)."""
    entry = _eval_group(spec["entry"], df)
    exit_ = _eval_group(spec["exit"], df)
    pos, out = 0.0, []
    ev, xv = entry.values, exit_.values
    for i in range(len(df)):
        if pos == 0.0 and ev[i]:
            pos = 1.0
        elif pos == 1.0 and xv[i]:
            pos = 0.0
        out.append(pos)
    return pd.Series(out, index=df.index)


def _describe_group(group: dict) -> str:
    joiner = " AND " if "all" in group else " OR "
    items = group.get("all", group.get("any", []))
    parts = []
    for it in items:
        if "all" in it or "any" in it:
            parts.append(f"({_describe_group(it)})")
        else:
            parts.append(f"{it['left']} {it['op'].replace('_', ' ')} {it['right']}")
    return joiner.join(parts)


def describe(spec: dict) -> str:
    """Plain-English summary of the rules."""
    name = spec.get("name", "Custom strategy")
    return (f"**{name}** — go long when {_describe_group(spec['entry'])}; "
            f"exit to cash when {_describe_group(spec['exit'])}.")
