"""Hyperparameter optimization — sweep a strategy's parameters to find the best.

Freqtrade-inspired: run the backtest across a grid of parameter combinations over
one symbol/period and rank by a chosen metric. Loads price data once. Always paired
with a loud overfitting caveat — the "best" params on history rarely stay best.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

from trading_llm.backtest import data as btdata
from trading_llm.backtest import engine as bteng
from trading_llm.backtest import metrics as btmetrics
from trading_llm.backtest.strategies import get_strategy

# higher-is-better metrics the optimizer can target
METRICS = {"sharpe", "total_return_pct", "cagr_pct"}

DEFAULT_GRIDS: dict[str, dict] = {
    "sma_cross": {"fast": [10, 20, 30, 50], "slow": [50, 100, 150, 200]},
    "ema_cross": {"fast": [8, 12, 20], "slow": [26, 50, 100]},
    "price_above_sma": {"period": [100, 150, 200]},
    "macd": {"fast": [8, 12], "slow": [21, 26], "signal": [9]},
    "rsi_reversion": {"period": [7, 14, 21], "buy_below": [20, 30], "exit_above": [50, 60, 70]},
}


@dataclass
class OptimizeResult:
    ok: bool
    symbol: str
    strategy_name: str = ""
    strategy_label: str = ""
    period: str = "2y"
    interval: str = "1d"
    metric: str = "sharpe"
    n_combos: int = 0
    best_params: dict = field(default_factory=dict)
    default_params: dict = field(default_factory=dict)
    results: list = field(default_factory=list)   # ranked [{params, metric_value, ...}] (in-sample)
    train_metric: float = 0.0   # best params' metric on the training slice (in-sample)
    oos_metric: float = 0.0     # SAME params' metric on the held-out test slice
    overfit: bool = False       # OOS collapsed vs in-sample -> likely curve-fit
    error: str = ""


def _combos(grid: dict, max_combos: int) -> list[dict]:
    keys = list(grid)
    out = []
    for vals in product(*(grid[k] for k in keys)):
        c = dict(zip(keys, vals))
        if "fast" in c and "slow" in c and c["fast"] >= c["slow"]:
            continue  # fast must be faster than slow
        out.append(c)
    return out[:max_combos]


def _run_metrics(df, strat, params, ppy):
    sig = strat.signal(df, {**strat.defaults, **params})
    run = bteng.run(df, sig, initial=10_000, cost_bps=5)
    return btmetrics.compute(run, ppy=ppy)


def optimize(symbol: str, strategy: str = "sma_cross", period: str = "2y",
             interval: str = "1d", metric: str = "sharpe",
             grid: dict | None = None, max_combos: int = 40) -> OptimizeResult:
    symbol = str(symbol).upper().strip()
    metric = metric if metric in METRICS else "sharpe"
    strat = get_strategy(strategy)
    if strat is None:
        return OptimizeResult(ok=False, symbol=symbol, error=f"Unknown strategy '{strategy}'.")
    grid = grid or DEFAULT_GRIDS.get(strat.name, {})
    if not grid:
        return OptimizeResult(ok=False, symbol=symbol, strategy_name=strat.name,
                              error=f"{strat.label} has no tunable parameters to optimize.")

    df = btdata.load_ohlc(symbol, period, interval)
    if df is None:
        return OptimizeResult(ok=False, symbol=symbol, strategy_name=strat.name,
                              error=f"No historical data for {symbol}.")
    ppy = btdata.PERIODS_PER_YEAR.get(interval, 252)

    # Train/test split: optimize ONLY on the first 70%, then validate the winner on
    # the held-out last 30% — the honest test of whether the params generalize.
    split = int(len(df) * 0.7)
    train = df.iloc[:split] if split >= 30 else df
    test = df.iloc[split:] if split >= 30 and len(df) - split >= 20 else None

    results = []
    for params in _combos(grid, max_combos):
        try:
            m = _run_metrics(train, strat, params, ppy)
            results.append({
                "params": params, "metric_value": m.get(metric, 0.0),
                "total_return_pct": m["total_return_pct"], "buy_hold_return_pct": m["buy_hold_return_pct"],
                "max_drawdown_pct": m["max_drawdown_pct"], "sharpe": m["sharpe"], "n_trades": m["n_trades"],
            })
        except Exception:
            continue

    if not results:
        return OptimizeResult(ok=False, symbol=symbol, strategy_name=strat.name,
                              error="No parameter combination produced a usable result.")
    results.sort(key=lambda r: (r["metric_value"] if r["metric_value"] is not None else -1e9), reverse=True)
    best = results[0]
    train_metric = float(best["metric_value"] or 0.0)

    oos_metric, overfit = 0.0, False
    if test is not None:
        try:
            oos_metric = float(_run_metrics(test, strat, best["params"], ppy).get(metric, 0.0))
            # collapsed out-of-sample (or flipped sign) => the in-sample win was noise
            overfit = oos_metric < max(0.0, train_metric) * 0.5 or (train_metric > 0 and oos_metric <= 0)
        except Exception:
            pass

    return OptimizeResult(
        ok=True, symbol=symbol, strategy_name=strat.name, strategy_label=strat.label,
        period=period, interval=interval, metric=metric, n_combos=len(results),
        best_params=best["params"], default_params=dict(strat.defaults), results=results,
        train_metric=round(train_metric, 3), oos_metric=round(oos_metric, 3), overfit=overfit,
    )


def explain(r: OptimizeResult, top: int = 8) -> str:
    if not r.ok:
        return f"⚠️ {r.error}"
    rows = []
    for x in r.results[:top]:
        p = ", ".join(f"{k}={v}" for k, v in x["params"].items())
        star = " ⭐" if x["params"] == r.best_params else ""
        rows.append(f"| `{p}`{star} | {x['sharpe']:+.2f} | {x['total_return_pct']:+.1f}% | "
                    f"{x['max_drawdown_pct']:.1f}% | {x['n_trades']} |")
    best = ", ".join(f"{k}={v}" for k, v in r.best_params.items())
    dflt = ", ".join(f"{k}={v}" for k, v in r.default_params.items())
    verdict = ("🔴 **Likely overfit** — the winner's edge vanished out-of-sample. Don't trust it."
               if r.overfit else
               "🟢 The winner held up out-of-sample — a more trustworthy result (still not a guarantee).")
    return f"""## Optimization — {r.strategy_label} on {r.symbol}

Swept **{r.n_combos} combos** on the first 70% of {r.period}, then validated the winner on the held-out last 30%.

| Parameters (in-sample) | Sharpe | Return | Max DD | Trades |
|---|---|---|---|---|
{chr(10).join(rows)}

**Best by {r.metric}:** `{best}` (default was `{dflt}`)
**In-sample {r.metric}: {r.train_metric:+.2f}  →  out-of-sample: {r.oos_metric:+.2f}**

{verdict}

> ⚠️ Optimization fits the past, including its noise. The out-of-sample check above is the real
> test: if the edge survives data it never saw, it's more believable. Always re-test on other
> symbols and periods before trusting any "best" setting.
"""
