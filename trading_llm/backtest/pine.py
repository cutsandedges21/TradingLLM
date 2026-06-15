"""Export a rule-DSL strategy to TradingView Pine Script v6."""
from __future__ import annotations

import re

_IND_RE = re.compile(r"^([a-z_]+)\((\d+)\)$")
_OP_PINE = {"<": "<", ">": ">", "<=": "<=", ">=": ">=", "==": "=="}


def _operand(token, decls: set) -> str:
    t = str(token).strip().lower()
    try:
        float(t)
        return t
    except ValueError:
        pass
    m = _IND_RE.match(t)
    if m:
        fn, n = m.group(1), int(m.group(2))
        return f"ta.{fn}(close, {n})"
    if t in ("macd_hist", "macd"):
        decls.add("macd")
        return "macdHist"
    return t  # close/open/high/low/volume


def _cond(c: dict, decls: set) -> str:
    left = _operand(c["left"], decls)
    right = _operand(c["right"], decls)
    op = c["op"]
    if op == "crosses_above":
        return f"ta.crossover({left}, {right})"
    if op == "crosses_below":
        return f"ta.crossunder({left}, {right})"
    return f"({left} {_OP_PINE.get(op, op)} {right})"


def _group(g: dict, decls: set) -> str:
    joiner = " and " if "all" in g else " or "
    items = g.get("all", g.get("any", []))
    parts = [(_group(it, decls) if ("all" in it or "any" in it) else _cond(it, decls)) for it in items]
    return joiner.join(parts) if parts else "false"


def to_pine(spec: dict) -> str:
    name = str(spec.get("name", "Custom Strategy")).replace('"', "'")
    decls: set = set()
    entry = _group(spec["entry"], decls)
    exit_ = _group(spec["exit"], decls)

    decl_lines = []
    if "macd" in decls:
        decl_lines.append("[macdLine, signalLine, macdHist] = ta.macd(close, 12, 26, 9)")

    body = "\n".join(decl_lines)
    if body:
        body += "\n"
    return f"""//@version=6
strategy("{name}", overlay=true, margin_long=100, margin_short=100)

{body}longCondition = {entry}
exitCondition = {exit_}

if (longCondition)
    strategy.entry("Long", strategy.long)
if (exitCondition)
    strategy.close("Long")

plotshape(longCondition, title="Buy", style=shape.triangleup, location=location.belowbar, color=color.green, size=size.tiny)
plotshape(exitCondition, title="Exit", style=shape.triangledown, location=location.abovebar, color=color.red, size=size.tiny)
"""
