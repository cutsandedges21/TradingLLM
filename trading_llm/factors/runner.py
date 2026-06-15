"""Bench the factor zoo over a universe + period → ranked, explainable results."""
from __future__ import annotations

from dataclasses import dataclass, field

from trading_llm.factors.panel import build_panel
from trading_llm.factors.library import REGISTRY, get_factor
from trading_llm.factors.scoring import (
    forward_returns, compute_ic_series, ic_stats, quantile_spread, classify,
)

# A liquid, diversified US large-cap universe. ~40 names gives a far less noisy
# cross-section than a handful — IC on a tiny universe is statistically unreliable.
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
    "MA", "UNH", "HD", "PG", "COST", "XOM", "JNJ", "WMT", "ORCL", "BAC",
    "KO", "PEP", "CSCO", "ADBE", "CRM", "AMD", "NFLX", "MCD", "ABBV", "CVX",
    "TMO", "ACN", "LIN", "DHR", "TXN", "QCOM", "NKE", "PM", "INTC", "GE",
]


def clean_universe(symbols: list[str]) -> list[str]:
    """Keep only plain equities — drop crypto (BTC/USD) and futures (GC=F) so the
    cross-section is apples-to-apples on one trading calendar."""
    out = []
    for s in symbols:
        u = str(s).upper().strip()
        if "/" in u or u.endswith("-USD") or "=" in u or "." in u:
            continue
        if u and u not in out:
            out.append(u)
    return out


@dataclass
class BenchResult:
    ok: bool
    universe: list = field(default_factory=list)
    period: str = "2y"
    horizon: int = 5
    n_symbols: int = 0
    n_days: int = 0
    start_date: str = ""
    end_date: str = ""
    results: list = field(default_factory=list)   # ranked factor dicts
    error: str = ""


def _bench_one(factor, panel, fwd) -> dict:
    try:
        fdf = factor.compute(panel)
        ic = compute_ic_series(fdf, fwd)
        stats = ic_stats(ic)
        spread = quantile_spread(fdf, fwd)
        strength, direction = classify(stats["ic_mean"], stats["ir"])
        return {
            "ok": True, "name": factor.name, "label": factor.label,
            "category": factor.category, "description": factor.description,
            "formula": factor.formula, "spread_pct": round(spread, 3),
            "strength": strength, "direction": direction, **stats,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "name": factor.name, "label": factor.label, "error": str(exc)}


def bench(universe: list[str] | None = None, period: str = "2y", interval: str = "1d",
          horizon: int = 5, factor_names: list[str] | None = None) -> BenchResult:
    uni = [s.upper() for s in (universe or DEFAULT_UNIVERSE)]
    panel = build_panel(uni, period, interval)
    if panel is None:
        return BenchResult(ok=False, universe=uni, period=period, horizon=horizon,
                           error="Could not assemble a panel — need at least ~5 equities "
                                 "with history (crypto is excluded from cross-sectional factors).")

    fwd = forward_returns(panel["close"], horizon)
    if factor_names:
        factors = [f for f in (get_factor(n) for n in factor_names) if f]
    else:
        factors = list(REGISTRY.values())

    results = [_bench_one(f, panel, fwd) for f in factors]
    ok_results = [r for r in results if r.get("ok")]
    # rank by consistency (|IR|) then strength (|IC mean|)
    ok_results.sort(key=lambda r: (abs(r["ir"]), abs(r["ic_mean"])), reverse=True)

    close = panel["close"]
    return BenchResult(
        ok=True, universe=panel.get("_symbols", uni), period=period, horizon=horizon,
        n_symbols=len(panel.get("_symbols", uni)), n_days=len(close),
        start_date=str(close.index[0])[:10], end_date=str(close.index[-1])[:10],
        results=ok_results + [r for r in results if not r.get("ok")],
    )
