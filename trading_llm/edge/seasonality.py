"""Seasonality / calendar anomalies — pure, from price history alone.

Month-of-year, day-of-week, and turn-of-month effects are documented (if weak)
anomalies; because they need no special data and are low-capacity, big funds
largely ignore them — which is exactly why a small account can lean on them.
All pure functions: feed dated daily closes, get JSON-friendly stats.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean

MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _monthly_last_closes(dates: list, closes: list[float]):
    last: dict[tuple, float] = {}
    for d, c in zip(dates, closes):
        last[(d.year, d.month)] = c
    keys = sorted(last)
    return keys, [last[k] for k in keys]


def monthly_returns(dates: list, closes: list[float]) -> list[tuple[int, float]]:
    """List of (month_of_year, month-over-month return)."""
    keys, mc = _monthly_last_closes(dates, closes)
    out = []
    for i in range(1, len(mc)):
        if mc[i - 1]:
            out.append((keys[i][1], mc[i] / mc[i - 1] - 1.0))
    return out


def _stats(rets: list[float]) -> dict:
    n = len(rets)
    return {
        "avg_pct": round(mean(rets) * 100, 2) if n else 0.0,
        "win_rate": round(sum(1 for r in rets if r > 0) / n * 100, 0) if n else 0.0,
        "n": n,
    }


def analyze(dates: list, closes: list[float], *, now_month: int | None = None) -> dict:
    """Seasonality profile. Needs ~2y+ of daily history."""
    if len(dates) < 252:
        return {"ok": False, "reason": "Need at least ~1 year of history for seasonality."}

    by_month: dict[int, list[float]] = defaultdict(list)
    for m, r in monthly_returns(dates, closes):
        by_month[m].append(r)
    months = {m: _stats(rs) for m, rs in sorted(by_month.items()) if rs}

    # day-of-week from daily returns
    by_dow: dict[int, list[float]] = defaultdict(list)
    for i in range(1, len(closes)):
        if closes[i - 1]:
            by_dow[dates[i].weekday()].append(closes[i] / closes[i - 1] - 1.0)
    day_of_week = {DOW[wd]: round(mean(v) * 100, 3) for wd, v in sorted(by_dow.items()) if v and wd < 5}

    # turn-of-month: last trading day + first 3 of next month vs all other days
    tom, rest = [], []
    for i in range(1, len(closes)):
        if not closes[i - 1]:
            continue
        r = closes[i] / closes[i - 1] - 1.0
        dom = dates[i].day
        (tom if (dom <= 3 or dom >= 28) else rest).append(r)
    tom_edge = (round((mean(tom) - mean(rest)) * 100, 3)
                if tom and rest else None)

    cur = now_month or datetime.now().month
    best = max(months.items(), key=lambda kv: kv[1]["avg_pct"]) if months else None
    worst = min(months.items(), key=lambda kv: kv[1]["avg_pct"]) if months else None
    years = round(len(monthly_returns(dates, closes)) / 12, 1)

    return {
        "ok": True,
        "current_month": cur,
        "current_month_name": MONTHS[cur],
        "current": months.get(cur),
        "months": {MONTHS[m]: s for m, s in months.items()},
        "best_month": {"name": MONTHS[best[0]], **best[1]} if best else None,
        "worst_month": {"name": MONTHS[worst[0]], **worst[1]} if worst else None,
        "day_of_week": day_of_week,
        "turn_of_month_edge_pct": tom_edge,
        "years": years,
        "note": "Calendar anomalies are weak, low-capacity, and not guaranteed — context, not a system.",
    }
