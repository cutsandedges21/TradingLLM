"""Signal learning loop — record signal-driven decisions, attribute outcomes, build base rates.

Closes the A→B→C arc honestly: when the user acts on a signal (or the committee
makes a signal-aware call), we log it; once enough time passes we fetch the realized
**alpha vs SPY** and mark win/loss; then we aggregate **base rates** by (kind, regime)
that feed both the Smart-Money Analyst's prompt and the UI. "Learning" here is a
reflection/base-rate loop — no model training — and it always shows its sample size.
"""
from __future__ import annotations

from datetime import datetime
from threading import Lock

from trading_llm.core.paths import MEMORY_DIR, load_json, save_json
from trading_llm.brain.reflection.outcomes import fetch_returns

JOURNAL_PATH = MEMORY_DIR / "signal_journal.json"
DEFAULT_HORIZON = 60
_lock = Lock()


def _load() -> list:
    data = load_json(JOURNAL_PATH, [])
    return data if isinstance(data, list) else []


def _save(data: list) -> None:
    save_json(JOURNAL_PATH, data)


def record(symbol: str, kind: str, regime_label: str, decision_date: str | None = None,
           side: str = "buy", note: str = "") -> dict:
    """Append a pending signal-driven decision to the journal."""
    entry = {
        "symbol": str(symbol).upper(),
        "kind": kind,
        "regime": regime_label or "unknown",
        "date": str(decision_date or datetime.now().strftime("%Y-%m-%d")),
        "side": side,
        "note": note,
        "created": datetime.now().isoformat(timespec="seconds"),
        "raw_return": None,
        "alpha_return": None,
        "win": None,
        "resolved": False,
    }
    with _lock:
        data = _load()
        data.append(entry)
        _save(data)
    return entry


def _days_since(date_str: str) -> int:
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
        return (datetime.now().date() - d).days
    except Exception:
        return 0


def resolve_pending(horizon_days: int = DEFAULT_HORIZON, fetch=fetch_returns) -> int:
    """Attach realized alpha to entries older than the horizon. Idempotent. Fail-soft.

    ``fetch`` is injectable so tests can run without network."""
    changed = 0
    with _lock:
        data = _load()
        for e in data:
            if e.get("resolved") or _days_since(e.get("date", "")) < horizon_days:
                continue
            try:
                raw, alpha, days = fetch(e["symbol"], e["date"], holding_days=horizon_days)
            except Exception:
                raw = alpha = days = None
            if raw is None or alpha is None:
                continue
            # For a long, alpha>0 is a win; for a short idea, invert.
            edge = alpha if e.get("side", "buy") == "buy" else -alpha
            e["raw_return"] = round(raw, 4)
            e["alpha_return"] = round(alpha, 4)
            e["holding_days"] = days
            e["win"] = bool(edge > 0)
            e["resolved"] = True
            changed += 1
        if changed:
            _save(data)
    return changed


def _agg(entries: list) -> dict:
    resolved = [e for e in entries if e.get("resolved") and e.get("alpha_return") is not None]
    n = len(resolved)
    wins = sum(1 for e in resolved if e.get("win"))
    avg_alpha = sum(e["alpha_return"] for e in resolved) / n if n else 0.0
    return {
        "n": n,
        "wins": wins,
        "win_rate_pct": round(wins / n * 100, 1) if n else 0.0,
        "avg_alpha_pct": round(avg_alpha * 100, 2),
    }


def base_rates() -> dict:
    """Overall + by (kind, regime) base rates over resolved entries."""
    data = _load()
    by_group: dict[str, dict] = {}
    groups: dict[str, list] = {}
    for e in data:
        key = f"{e.get('kind', '?')}|{e.get('regime', '?')}"
        groups.setdefault(key, []).append(e)
    for key, items in groups.items():
        agg = _agg(items)
        if agg["n"]:
            by_group[key] = agg
    return {
        "overall": _agg(data),
        "by_group": by_group,
        "pending": sum(1 for e in data if not e.get("resolved")),
        "total": len(data),
    }


def track_record_context() -> str:
    """Compact track-record string for the analyst prompt + UI. '' when no resolved data."""
    br = base_rates()
    o = br["overall"]
    if not o["n"]:
        return ""
    lines = [f"[DESK TRACK RECORD — signal-driven paper calls, vs SPY @ {DEFAULT_HORIZON}d]"]
    lines.append(f"  Overall: {o['wins']}/{o['n']} beat SPY ({o['win_rate_pct']:.0f}%), "
                 f"avg alpha {o['avg_alpha_pct']:+.1f}%.")
    for key, agg in sorted(br["by_group"].items(), key=lambda kv: -kv[1]["n"]):
        kind, regime = key.split("|")
        lines.append(f"  {kind} in {regime}: {agg['wins']}/{agg['n']} "
                     f"({agg['win_rate_pct']:.0f}%), avg alpha {agg['avg_alpha_pct']:+.1f}%.")
    if o["n"] < 10:
        lines.append("  (Small, young sample — treat as weak evidence.)")
    return "\n".join(lines)


def view() -> dict:
    """For the API/UI."""
    return base_rates()
