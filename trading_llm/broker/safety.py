"""Safety model for opt-in real (Alpaca paper) trading.

Real routing is OFF by default — the local mock broker handles everything unless the
user explicitly commits a **mandate** (enables it + sets caps). Even then, every
order passes a pre-trade **guard** (kill-switch, symbol universe, per-order size,
daily count), and every attempt is written to an **audit** log. Ported in spirit
from Vibe-Trading's mandate / order-guard / kill-switch.
"""
from __future__ import annotations

from datetime import datetime, date

from trading_llm.core.paths import MEMORY_DIR, load_json, save_json

HALT_FILE = MEMORY_DIR / "HALT"
AUDIT_PATH = MEMORY_DIR / "broker_audit.json"

DEFAULT_MANDATE = {
    "enabled": False,            # master opt-in for real (Alpaca paper) routing
    "max_order_usd": 1000.0,     # largest single order allowed
    "max_trades_per_day": 5,     # daily cap on live orders
    "allowed_symbols": [],       # empty = any symbol; else an allow-list
}


# ---------- kill-switch (filesystem flag = instant, survives restarts) ----------
def is_halted() -> bool:
    return HALT_FILE.exists()


def halt() -> bool:
    HALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HALT_FILE.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    audit("halt", {"detail": "kill-switch engaged"})
    return True


def resume() -> bool:
    existed = HALT_FILE.exists()
    if existed:
        try:
            HALT_FILE.unlink()
        except Exception:
            return False
    audit("resume", {"detail": "kill-switch cleared"})
    return existed


# ---------- audit ----------
def audit(action: str, detail: dict | None = None) -> None:
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), "action": action}
    entry.update(detail or {})
    data = load_json(AUDIT_PATH, [])
    if not isinstance(data, list):
        data = []
    data.append(entry)
    save_json(AUDIT_PATH, data[-500:])  # keep the tail bounded


def audit_log(n: int = 50) -> list:
    data = load_json(AUDIT_PATH, [])
    return data[-n:] if isinstance(data, list) else []


# ---------- pre-trade order guard ----------
def check_order(proposal: dict, est_cost: float | None,
                trades_today: int, mandate: dict) -> tuple[bool, str]:
    """Return (ok, reason). Fail-closed: any doubt blocks the order."""
    if is_halted():
        return False, "🛑 Kill-switch is engaged — live trading is halted. Resume it to trade."
    if not mandate.get("enabled"):
        return False, "Live trading is disabled (it's off by default). Commit a mandate to enable it."

    sym = str(proposal.get("symbol", "")).upper()
    if not sym:
        return False, "No symbol on the order."

    allowed = [s.upper() for s in mandate.get("allowed_symbols", []) if s]
    if allowed and sym not in allowed:
        return False, f"{sym} is not in your committed symbol universe ({', '.join(allowed)})."

    max_usd = float(mandate.get("max_order_usd", 0) or 0)
    if est_cost is not None and max_usd and est_cost > max_usd:
        return False, f"Order ~${est_cost:,.0f} exceeds your committed per-order cap of ${max_usd:,.0f}."

    cap = int(mandate.get("max_trades_per_day", 0) or 0)
    if cap and trades_today >= cap:
        return False, f"Daily live-trade cap reached ({cap}). Resets tomorrow."

    return True, "ok"
