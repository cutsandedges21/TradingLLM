"""Pure data types for the smart-money signals subsystem (Phase A).

No I/O here — just dataclasses + deterministic aggregation, so everything is
trivially unit-testable. A ``Signal`` is one normalized datum from any source
(insider Form 4, institutional 13F, congressional disclosure); a ``SignalBundle``
is the merged, aggregated view for one symbol; ``Regime`` is the market-wide state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

# Signal kinds (kept as plain strings so they serialize cleanly to JSON).
INSIDER_BUY = "insider_buy"
INSIDER_SELL = "insider_sell"
INST_13F = "inst_13f"
CONGRESS = "congress"


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _days_ago(d: str, now: date) -> int | None:
    pd = _parse_date(d)
    return (now - pd).days if pd else None


@dataclass
class Signal:
    """One normalized smart-money datum from any source."""
    kind: str           # INSIDER_BUY | INSIDER_SELL | INST_13F | CONGRESS
    symbol: str
    date: str           # transaction/report date "YYYY-MM-DD"
    actor: str          # "Arthur D Levinson (Director)" | "Berkshire Hathaway" | "Sen. Jane Roe"
    direction: int      # +1 bought/added, -1 sold/trimmed
    size_usd: float = 0.0   # best-effort notional; 0.0 when unknown
    detail: str = ""
    source_url: str = ""
    as_of: str = ""     # when fetched "YYYY-MM-DD"
    lag_note: str = ""  # "~2-day lag" | "~45-day lag (last quarter)" | "varies"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "symbol": self.symbol, "date": self.date,
            "actor": self.actor, "direction": self.direction,
            "size_usd": round(self.size_usd, 2), "detail": self.detail,
            "source_url": self.source_url, "as_of": self.as_of, "lag_note": self.lag_note,
        }

    @staticmethod
    def from_dict(d: dict) -> "Signal":
        return Signal(
            kind=d.get("kind", ""), symbol=d.get("symbol", ""), date=d.get("date", ""),
            actor=d.get("actor", ""), direction=int(d.get("direction", 0)),
            size_usd=float(d.get("size_usd", 0.0)), detail=d.get("detail", ""),
            source_url=d.get("source_url", ""), as_of=d.get("as_of", ""),
            lag_note=d.get("lag_note", ""),
        )


@dataclass
class SignalBundle:
    """Merged, aggregated smart-money view for one symbol."""
    symbol: str
    signals: list[Signal] = field(default_factory=list)
    net_insider_usd_30d: float = 0.0
    net_insider_usd_90d: float = 0.0
    insider_buys_30d: int = 0
    insider_sells_30d: int = 0
    funds_holding: int = 0
    congress_trades_90d: int = 0
    stale: bool = False
    sources_unavailable: list[str] = field(default_factory=list)

    @classmethod
    def build(cls, symbol: str, signals: list[Signal], *,
              funds_holding: int = 0, stale: bool = False,
              sources_unavailable: list[str] | None = None,
              now: date | None = None) -> "SignalBundle":
        now = now or datetime.now().date()
        net30 = net90 = 0.0
        buys30 = sells30 = congress90 = 0
        for s in signals:
            ago = _days_ago(s.date, now)
            if s.kind in (INSIDER_BUY, INSIDER_SELL):
                signed = s.direction * s.size_usd
                if ago is not None and ago <= 90:
                    net90 += signed
                    if ago <= 30:
                        net30 += signed
                        if s.kind == INSIDER_BUY:
                            buys30 += 1
                        else:
                            sells30 += 1
            elif s.kind == CONGRESS:
                if ago is not None and ago <= 90:
                    congress90 += 1
        # newest first for display
        ordered = sorted(signals, key=lambda x: x.date or "", reverse=True)
        return cls(
            symbol=symbol, signals=ordered,
            net_insider_usd_30d=round(net30, 2), net_insider_usd_90d=round(net90, 2),
            insider_buys_30d=buys30, insider_sells_30d=sells30,
            funds_holding=funds_holding, congress_trades_90d=congress90,
            stale=stale, sources_unavailable=sources_unavailable or [],
        )

    def has_data(self) -> bool:
        return bool(self.signals) or self.funds_holding > 0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "signals": [s.to_dict() for s in self.signals],
            "net_insider_usd_30d": self.net_insider_usd_30d,
            "net_insider_usd_90d": self.net_insider_usd_90d,
            "insider_buys_30d": self.insider_buys_30d,
            "insider_sells_30d": self.insider_sells_30d,
            "funds_holding": self.funds_holding,
            "congress_trades_90d": self.congress_trades_90d,
            "stale": self.stale,
            "sources_unavailable": self.sources_unavailable,
        }


@dataclass
class Regime:
    """Market-wide state, computed from price bars we already fetch."""
    ok: bool = False
    label: str = "unknown"      # risk_on | neutral | risk_off
    trend: str = "unknown"      # up | sideways | down
    vol: str = "unknown"        # low | normal | high
    breadth_pct: float = 0.0
    spy_vs_200dma_pct: float = 0.0
    realized_vol_20d: float = 0.0
    momentum_3m_pct: float = 0.0
    summary: str = ""
    as_of: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok, "label": self.label, "trend": self.trend, "vol": self.vol,
            "breadth_pct": round(self.breadth_pct, 1),
            "spy_vs_200dma_pct": round(self.spy_vs_200dma_pct, 2),
            "realized_vol_20d": round(self.realized_vol_20d, 1),
            "momentum_3m_pct": round(self.momentum_3m_pct, 2),
            "summary": self.summary, "as_of": self.as_of,
        }
