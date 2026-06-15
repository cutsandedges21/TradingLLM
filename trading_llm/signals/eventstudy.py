"""Event study — does a smart-money signal actually precede out-performance?

Pure, deterministic statistics (no I/O) so the logic is unit-testable with
synthetic data. Given a list of signal events and daily closes for the symbol +
SPY, it answers, per horizon: what was the forward return, the alpha vs SPY, the
symbol's *unconditional* baseline alpha (its normal drift), and therefore the
signal's marginal **edge** — with a t-stat and a chronological in-sample /
out-of-sample split so we never oversell a noisy or stale effect.

Honest by construction: past performance is not predictive; small samples and
weak t-stats are flagged, not hidden.
"""
from __future__ import annotations

import bisect
import math
from datetime import datetime, timedelta

DEFAULT_HORIZONS = (30, 60, 90)


def _to_date(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def forward_return(dates: list, closes: list[float], event_date, horizon_days: int):
    """Return the simple return from the first trading day >= event_date to the
    first trading day >= entry + horizon_days. None if history is insufficient."""
    if not dates:
        return None
    i = bisect.bisect_left(dates, event_date)
    if i >= len(dates):
        return None
    entry = dates[i]
    target = entry + timedelta(days=horizon_days)
    j = bisect.bisect_left(dates, target)
    if j >= len(dates) or closes[i] in (0, None):
        return None
    return closes[j] / closes[i] - 1.0


def _alpha(sd, sc, bd, bc, event_date, horizon):
    """Forward alpha (stock − SPY) for one event, or None if either side lacks data."""
    sr = forward_return(sd, sc, event_date, horizon)
    br = forward_return(bd, bc, event_date, horizon)
    if sr is None or br is None:
        return None, None
    return sr, sr - br


def baseline_alpha(sd, sc, bd, bc, horizon, lo, hi) -> float:
    """Mean forward alpha over *every* trading day in [lo, hi] — the symbol's
    unconditional drift vs SPY, so we can isolate the signal's marginal edge."""
    alphas = []
    for d in sd:
        if d < lo or d > hi:
            continue
        _r, a = _alpha(sd, sc, bd, bc, d, horizon)
        if a is not None:
            alphas.append(a)
    return _mean(alphas)


def event_study(events: list[dict], stock_dates: list, stock_closes: list[float],
                spy_dates: list, spy_closes: list[float],
                horizons=DEFAULT_HORIZONS) -> dict:
    """Run the study. ``events`` are dicts with a 'date' key (YYYY-MM-DD)."""
    ev_dates = sorted(d for d in (_to_date(e.get("date")) for e in events) if d)
    if not ev_dates or not stock_dates:
        return {"ok": False, "n_events": len(ev_dates),
                "reason": "Not enough events or price history for a study."}
    lo, hi = ev_dates[0], ev_dates[-1]

    rows = []
    for h in horizons:
        rets, alphas, ev_used = [], [], []
        for d in ev_dates:
            r, a = _alpha(stock_dates, stock_closes, spy_dates, spy_closes, d, h)
            if a is not None:
                rets.append(r)
                alphas.append(a)
                ev_used.append(d)
        n = len(alphas)
        base = baseline_alpha(stock_dates, stock_closes, spy_dates, spy_closes, h, lo, hi)
        mean_a = _mean(alphas)
        sd_a = _std(alphas)
        t = (mean_a / (sd_a / math.sqrt(n))) if (n > 1 and sd_a > 0) else 0.0
        # chronological IS/OOS split (events are already date-sorted via ev_dates)
        cut = int(n * 0.7)
        is_a = _mean(alphas[:cut]) if cut else 0.0
        oos_a = _mean(alphas[cut:]) if n - cut else 0.0
        hit = (sum(1 for a in alphas if a > 0) / n * 100.0) if n else 0.0
        rows.append({
            "horizon": h, "n": n,
            "mean_ret_pct": round(_mean(rets) * 100, 2),
            "mean_alpha_pct": round(mean_a * 100, 2),
            "baseline_alpha_pct": round(base * 100, 2),
            "edge_pct": round((mean_a - base) * 100, 2),
            "hit_rate_pct": round(hit, 1),
            "t_stat": round(t, 2),
            "is_alpha_pct": round(is_a * 100, 2),
            "oos_alpha_pct": round(oos_a * 100, 2),
            "n_is": cut, "n_oos": n - cut,
        })

    return {
        "ok": True, "n_events": len(ev_dates),
        "window": {"start": str(lo), "end": str(hi)},
        "horizons": rows,
        "verdict": _verdict(rows, len(ev_dates)),
    }


def _verdict(rows: list[dict], n_events: int) -> str:
    if n_events < 10:
        return (f"Only {n_events} events in the available window — far too few to conclude "
                "anything. Treat as anecdote, not evidence.")
    # Use the 60-day horizon if present, else the middle row.
    row = next((r for r in rows if r["horizon"] == 60), rows[len(rows) // 2])
    h, n, edge, t = row["horizon"], row["n"], row["edge_pct"], row["t_stat"]
    is_a, oos_a = row["is_alpha_pct"], row["oos_alpha_pct"]
    if abs(t) < 1.5:
        base = (f"No statistically meaningful effect at {h}d (edge {edge:+.1f}% vs SPY, "
                f"t={t:.1f}, n={n}) — indistinguishable from noise.")
    elif edge > 0:
        base = (f"Historically positive: after this signal, the stock beat SPY by ~{edge:+.1f}% "
                f"over {h}d (t={t:.1f}, n={n}).")
    else:
        base = (f"Historically negative: the stock *trailed* SPY by ~{edge:.1f}% over {h}d "
                f"after this signal (t={t:.1f}, n={n}).")
    # OOS stability note
    if (is_a > 0) != (oos_a > 0) and abs(t) >= 1.5:
        base += (f" ⚠️ It did not hold up out-of-sample (recent events {oos_a:+.1f}% vs "
                 f"earlier {is_a:+.1f}%).")
    return base + " Past performance is not predictive."


def explain(result: dict) -> str:
    """Plain-English multi-line summary for the chat/UI."""
    if not result.get("ok"):
        return result.get("reason", "Study unavailable.")
    w = result["window"]
    lines = [f"**{result['n_events']} events** ({w['start']} → {w['end']})", "", result["verdict"], ""]
    for r in result["horizons"]:
        lines.append(
            f"- **{r['horizon']}d** (n={r['n']}): return {r['mean_ret_pct']:+.1f}% · "
            f"alpha {r['mean_alpha_pct']:+.1f}% · edge {r['edge_pct']:+.1f}% · "
            f"hit {r['hit_rate_pct']:.0f}% · t={r['t_stat']:.1f}")
    return "\n".join(lines)
