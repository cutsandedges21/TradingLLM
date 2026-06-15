"""Position sizing, risk-of-ruin, portfolio heat, and the pre-trade checklist.

All pure functions. Conventions:
- ``risk_pct`` / ``risk_frac`` are fractions (0.01 == 1%).
- "Risk" on a trade = the dollars you'd lose if price hit your stop, NOT the
  position's notional. Sizing to a *fixed fraction of equity risked per trade* is
  what keeps a string of losers from ending the account.
"""
from __future__ import annotations

import math
import random

# Sensible defaults (overridable via settings["risk"]).
DEFAULT_ACCOUNT_RISK_PCT = 0.01     # risk 1% of equity per trade
DEFAULT_MAX_HEAT_PCT = 0.06         # total open risk cap = 6% of equity
DEFAULT_STOP_PCT = 0.10             # assumed stop distance when none is given
DEFAULT_MAX_POSITION_PCT = 0.20     # one name <= 20% of equity


def expectancy(win_rate: float, payoff: float) -> float:
    """Expected R per trade: p*payoff − (1−p). >0 means a positive-edge system."""
    return win_rate * payoff - (1.0 - win_rate)


def kelly_fraction(win_rate: float, payoff: float) -> float:
    """Full-Kelly fraction of equity to risk: f* = p − (1−p)/b. Clamped to [0,1]."""
    if payoff <= 0 or not (0.0 < win_rate < 1.0):
        return 0.0
    f = win_rate - (1.0 - win_rate) / payoff
    return max(0.0, min(1.0, f))


def suggested_risk_pct(win_rate: float, payoff: float, *, kelly_divisor: float = 4.0,
                       cap: float = 0.02) -> float:
    """Fractional-Kelly risk suggestion (quarter-Kelly by default), capped.

    Full Kelly is too aggressive for real, non-stationary edges — fractional Kelly
    keeps most of the growth with a fraction of the drawdown."""
    k = kelly_fraction(win_rate, payoff)
    return round(min(cap, k / kelly_divisor), 4)


def fixed_fractional_size(equity: float, risk_pct: float, entry: float, stop: float) -> dict:
    """Shares such that hitting ``stop`` loses exactly ``risk_pct`` of equity."""
    risk_dollars = max(0.0, equity * risk_pct)
    rps = abs(entry - stop)
    if rps <= 0 or entry <= 0:
        return {"shares": 0, "notional": 0.0, "risk_dollars": round(risk_dollars, 2),
                "risk_per_share": 0.0, "pct_of_equity": 0.0,
                "note": "Need a stop different from entry to size by risk."}
    shares = math.floor(risk_dollars / rps)
    notional = shares * entry
    return {
        "shares": shares,
        "notional": round(notional, 2),
        "risk_dollars": round(risk_dollars, 2),
        "risk_per_share": round(rps, 4),
        "pct_of_equity": round(notional / equity * 100, 2) if equity else 0.0,
    }


def atr_from_bars(highs: list[float] | None, lows: list[float] | None,
                  closes: list[float], period: int = 14) -> float | None:
    """Average True Range. Falls back to close-to-close range if H/L are absent."""
    n = len(closes)
    if n < period + 1:
        return None
    trs = []
    for i in range(1, n):
        if highs and lows and i < len(highs) and i < len(lows):
            h, l, pc = highs[i], lows[i], closes[i - 1]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        else:
            trs.append(abs(closes[i] - closes[i - 1]))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def risk_of_ruin(win_rate: float, payoff: float, risk_frac: float, *,
                 n_trades: int = 200, ruin_drawdown: float = 0.5,
                 sims: int = 3000, seed: int | None = 7) -> float:
    """Monte-Carlo probability of a peak-to-trough drawdown >= ``ruin_drawdown``
    over ``n_trades``, sizing each trade at ``risk_frac`` of equity (fixed-fractional)."""
    if risk_frac <= 0 or not (0.0 < win_rate < 1.0) or payoff <= 0:
        return 0.0
    rng = random.Random(seed)
    ruined = 0
    for _ in range(sims):
        equity = peak = 1.0
        for _ in range(n_trades):
            if rng.random() < win_rate:
                equity *= (1.0 + risk_frac * payoff)
            else:
                equity *= (1.0 - risk_frac)
            peak = max(peak, equity)
            if equity <= peak * (1.0 - ruin_drawdown):
                ruined += 1
                break
    return round(ruined / sims, 4)


def portfolio_heat(positions: list[dict], equity: float, *,
                   stop_pct: float = DEFAULT_STOP_PCT) -> dict:
    """Total open risk = sum over positions of (market value × assumed stop distance).

    Positions don't carry explicit stops here, so we estimate risk with a uniform
    ``stop_pct`` — conservative and good enough to flag an over-exposed book."""
    gross = 0.0
    open_risk = 0.0
    for p in positions or []:
        mv = abs(float(p.get("market_value") or 0.0))
        gross += mv
        open_risk += mv * stop_pct
    return {
        "gross_exposure": round(gross, 2),
        "gross_pct": round(gross / equity * 100, 2) if equity else 0.0,
        "open_risk": round(open_risk, 2),
        "open_risk_pct": round(open_risk / equity * 100, 2) if equity else 0.0,
        "n_positions": len(positions or []),
    }


def _check(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def pretrade_check(proposal: dict, equity: float, buying_power: float,
                   positions: list[dict], settings_risk: dict | None = None,
                   trades_today: int = 0) -> dict:
    """Run the proposed (paper) order through the survival rules. Returns a
    checklist of pass/warn/fail items + an overall verdict. Never raises."""
    r = settings_risk or {}
    max_pos_usd = float(r.get("max_position_usd", 2000))
    max_pos_pct = float(r.get("max_position_pct", DEFAULT_MAX_POSITION_PCT))
    max_heat_pct = float(r.get("max_portfolio_heat_pct", DEFAULT_MAX_HEAT_PCT))
    stop_pct = float(r.get("default_stop_pct", DEFAULT_STOP_PCT))
    max_trades = int(r.get("max_trades_per_day", 10))

    side = str(proposal.get("action", "buy")).lower()
    notional = proposal.get("notional")
    try:
        notional = float(notional) if notional else 0.0
    except Exception:
        notional = 0.0
    checks: list[dict] = []

    # 1) Per-trade size vs hard cap
    if notional <= 0:
        checks.append(_check("Order size", "warn", "No notional on the proposal to size-check."))
    elif notional > max_pos_usd:
        checks.append(_check("Order size", "fail",
                             f"~${notional:,.0f} exceeds your ${max_pos_usd:,.0f} per-trade cap."))
    else:
        checks.append(_check("Order size", "pass", f"~${notional:,.0f} within the ${max_pos_usd:,.0f} cap."))

    # 2) Concentration vs equity
    pct = (notional / equity * 100) if equity else 0.0
    if pct > max_pos_pct * 100:
        checks.append(_check("Concentration", "fail",
                             f"{pct:.1f}% of equity — above the {max_pos_pct*100:.0f}% single-name limit."))
    elif pct > max_pos_pct * 100 * 0.6:
        checks.append(_check("Concentration", "warn", f"{pct:.1f}% of equity is a chunky single name."))
    else:
        checks.append(_check("Concentration", "pass", f"{pct:.1f}% of equity."))

    # 3) Buying power (buys only)
    if side == "buy" and notional > 0:
        if notional > buying_power:
            checks.append(_check("Buying power", "fail",
                                 f"Needs ${notional:,.0f}, only ${buying_power:,.0f} available."))
        else:
            checks.append(_check("Buying power", "pass", f"${buying_power:,.0f} available."))

    # 4) Portfolio heat after adding this trade
    heat = portfolio_heat(positions, equity, stop_pct=stop_pct)
    added_risk_pct = (notional * stop_pct / equity * 100) if (equity and side == "buy") else 0.0
    total_heat = heat["open_risk_pct"] + added_risk_pct
    if total_heat > max_heat_pct * 100:
        checks.append(_check("Portfolio heat", "warn",
                             f"Est. total open risk ~{total_heat:.1f}% (cap {max_heat_pct*100:.0f}%). "
                             "Trim or tighten stops."))
    else:
        checks.append(_check("Portfolio heat", "pass",
                             f"Est. total open risk ~{total_heat:.1f}% of equity."))

    # 5) Stop / invalidation defined?
    has_stop = bool(proposal.get("stop") or proposal.get("limit_price")) or \
        "stop" in str(proposal.get("rationale", "")).lower() or \
        "invalidat" in str(proposal.get("rationale", "")).lower()
    checks.append(_check("Stop defined", "pass" if has_stop else "warn",
                         "Invalidation level present." if has_stop else
                         "No stop/invalidation — decide your exit before you enter."))

    # 6) Daily trade budget (overtrading guard)
    if trades_today >= max_trades:
        checks.append(_check("Daily budget", "fail", f"Already {trades_today}/{max_trades} trades today."))
    elif trades_today >= max_trades * 0.7:
        checks.append(_check("Daily budget", "warn", f"{trades_today}/{max_trades} trades today — slow down."))
    else:
        checks.append(_check("Daily budget", "pass", f"{trades_today}/{max_trades} trades today."))

    fails = sum(1 for c in checks if c["status"] == "fail")
    warns = sum(1 for c in checks if c["status"] == "warn")
    verdict = "fail" if fails else ("warn" if warns else "pass")
    headline = {
        "fail": "Breaks a risk rule — reconsider or resize.",
        "warn": "Allowed, but mind the flagged risks.",
        "pass": "Within your risk rules.",
    }[verdict]
    return {"verdict": verdict, "headline": headline, "fails": fails, "warns": warns, "checks": checks}
