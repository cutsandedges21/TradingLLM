"""High-level backtest entry point: spec in, structured result out."""
from __future__ import annotations

from dataclasses import dataclass, field

from trading_llm.backtest import data as btdata
from trading_llm.backtest import engine as btengine
from trading_llm.backtest import metrics as btmetrics
from trading_llm.backtest.strategies import get_strategy


@dataclass
class BacktestResult:
    ok: bool
    symbol: str
    strategy_name: str = ""
    strategy_label: str = ""
    strategy_desc: str = ""
    params: dict = field(default_factory=dict)
    period: str = "2y"
    interval: str = "1d"
    n_bars: int = 0
    start_date: str = ""
    end_date: str = ""
    metrics: dict = field(default_factory=dict)
    equity_curve: list = field(default_factory=list)   # [{date, equity, benchmark}]
    trades: list = field(default_factory=list)
    error: str = ""


def _downsample(result, max_points: int = 120) -> list:
    eq, bench = result.equity, result.benchmark
    n = len(eq)
    step = max(1, n // max_points)
    out = []
    for i in range(0, n, step):
        out.append({
            "date": str(eq.index[i])[:10],
            "equity": round(float(eq.iloc[i]), 2),
            "benchmark": round(float(bench.iloc[i]), 2),
        })
    return out


def backtest(symbol: str, strategy: str = "sma_cross", params: dict | None = None,
             period: str = "2y", interval: str = "1d",
             initial: float = 10_000.0, cost_bps: float = 5.0) -> BacktestResult:
    symbol = str(symbol).upper().strip()
    strat = get_strategy(strategy)
    if strat is None:
        return BacktestResult(ok=False, symbol=symbol,
                              error=f"Unknown strategy '{strategy}'. Try one of: "
                                    "buy_hold, sma_cross, ema_cross, price_above_sma, macd, rsi_reversion.")

    df = btdata.load_ohlc(symbol, period, interval)
    if df is None:
        return BacktestResult(ok=False, symbol=symbol, strategy_name=strat.name,
                              error=f"No historical data available for {symbol} "
                                    f"({period}/{interval}). Check the ticker.")

    merged = {**strat.defaults, **(params or {})}
    try:
        signal = strat.signal(df, merged)
        run = btengine.run(df, signal, initial=initial, cost_bps=cost_bps)
    except Exception as exc:  # noqa: BLE001
        return BacktestResult(ok=False, symbol=symbol, strategy_name=strat.name,
                              error=f"Backtest failed: {exc}")

    ppy = btdata.PERIODS_PER_YEAR.get(interval, 252)
    metrics = btmetrics.compute(run, ppy=ppy)
    trades = [t.__dict__ for t in run.trades]

    return BacktestResult(
        ok=True, symbol=symbol, strategy_name=strat.name, strategy_label=strat.label,
        strategy_desc=strat.description, params=merged, period=period, interval=interval,
        n_bars=len(df), start_date=str(df.index[0])[:10], end_date=str(df.index[-1])[:10],
        metrics=metrics, equity_curve=_downsample(run), trades=trades,
    )
