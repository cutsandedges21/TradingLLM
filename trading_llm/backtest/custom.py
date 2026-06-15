"""Run a rule-DSL strategy: compile → backtest → explain → Pine Script."""
from __future__ import annotations

from trading_llm.backtest import data as btdata
from trading_llm.backtest import engine as bteng
from trading_llm.backtest import metrics as btmetrics
from trading_llm.backtest.dsl import validate, compile_signal, describe
from trading_llm.backtest.pine import to_pine


def _explain(res: dict) -> str:
    m = res["metrics"]
    sign = lambda x: f"{x:+.2f}"  # noqa: E731
    return f"""## Custom strategy — {res['name']} on {res['symbol']}

{res['rules']}

**Window:** {res['start_date']} → {res['end_date']} · {res['n_bars']} bars

| Metric | Strategy | Buy & Hold |
|---|---|---|
| Total return | {sign(m['total_return_pct'])}% | {sign(m['buy_hold_return_pct'])}% |
| Max drawdown | {m['max_drawdown_pct']:.1f}% | {m['buy_hold_max_drawdown_pct']:.1f}% |
| Sharpe | {m['sharpe']:.2f} | — |
| Trades · win rate | {m['n_trades']} · {m['win_rate_pct']:.0f}% | — |

### 📈 TradingView Pine Script v6
Paste this into TradingView's Pine Editor to run your strategy there:
```pine
{res['pine']}
```

> Generated from your description, then backtested honestly (next-bar fills, a small
> cost, look-ahead banned). One symbol over one window isn't proof — re-test on
> others, and remember a rule tuned to past data often disappoints live.
"""


def run_custom(spec: dict, symbol: str, period: str = "2y", interval: str = "1d",
               initial: float = 10_000.0, cost_bps: float = 5.0) -> dict:
    ok, err = validate(spec)
    if not ok:
        return {"ok": False, "error": err}
    symbol = str(symbol).upper().strip()
    df = btdata.load_ohlc(symbol, period, interval)
    if df is None:
        return {"ok": False, "error": f"No historical data for {symbol}."}
    try:
        signal = compile_signal(spec, df)
        run = bteng.run(df, signal, initial=initial, cost_bps=cost_bps)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Could not run the strategy: {exc}"}

    ppy = btdata.PERIODS_PER_YEAR.get(interval, 252)
    m = btmetrics.compute(run, ppy=ppy)
    eq, bench = run.equity, run.benchmark
    step = max(1, len(eq) // 120)
    curve = [{"date": str(eq.index[i])[:10], "equity": round(float(eq.iloc[i]), 2),
              "benchmark": round(float(bench.iloc[i]), 2)} for i in range(0, len(eq), step)]

    res = {
        "ok": True, "symbol": symbol, "name": spec.get("name", "Custom strategy"),
        "rules": describe(spec), "spec": spec, "metrics": m, "equity_curve": curve,
        "trades": [t.__dict__ for t in run.trades][-10:],
        "n_bars": len(df), "start_date": str(df.index[0])[:10], "end_date": str(df.index[-1])[:10],
        "pine": to_pine(spec),
    }
    res["explanation"] = _explain(res)
    return res
