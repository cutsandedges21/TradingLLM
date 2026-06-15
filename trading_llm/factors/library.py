"""The factor zoo — cross-sectional alpha signals, each with a teaching note.

A factor maps an OHLCV ``panel`` (dict of wide DataFrames) to a wide DataFrame of
scores: for each date, a number per symbol whose cross-sectional *ranking* is
meant to predict the next few days' returns. Mix of well-known academic factors
and a faithful subset of Kakushadze (2015) "101 Formulaic Alphas".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from trading_llm.factors import operators as op


def _rsi(close: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ── classic factors ──
def f_momentum_120(p):  # 6-month price momentum
    return op.rank(op.safe_div(op.delta(p["close"], 120), p["close"].shift(120)))


def f_momentum_252_21(p):  # Carhart 12m-1m
    long = op.safe_div(op.delta(p["close"], 252), p["close"].shift(252))
    short = op.safe_div(op.delta(p["close"], 21), p["close"].shift(21))
    return op.cs_zscore(long - short)


def f_reversal_5(p):  # short-term reversal (buy recent losers)
    return op.rank(-1.0 * p["close"].pct_change(5))


def f_low_volatility(p):  # low-vol anomaly (calmer names score higher)
    return op.rank(-1.0 * op.ts_std(p["returns"], 20))


def f_rsi_oversold(p):  # mean reversion on RSI
    return op.rank(50.0 - _rsi(p["close"], 14))


def f_volume_surge(p):  # recent volume vs its baseline
    return op.rank(op.safe_div(op.ts_mean(p["volume"], 5), op.ts_mean(p["volume"], 20)))


def f_near_high(p):  # proximity to the 20-day high (breakout tendency)
    return op.rank(op.safe_div(p["close"], op.ts_max(p["high"], 20)))


# ── Kakushadze alpha101 subset (faithful) ──
def f_alpha006(p):  # -1 * correlation(open, volume, 10)
    return -1.0 * op.ts_corr(p["open"], p["volume"], 10)


def f_alpha012(p):  # sign(delta(volume,1)) * (-1 * delta(close,1))
    return np.sign(op.delta(p["volume"], 1)) * (-1.0 * op.delta(p["close"], 1))


def f_alpha101(p):  # (close - open) / (high - low + .001)
    return (p["close"] - p["open"]) / (p["high"] - p["low"] + 0.001)


def f_alpha001(p):  # rank(ts_argmax(signed_power(x, 2), 5)) - 0.5
    returns = p["close"].pct_change()
    cond = (returns < 0).astype(float)
    x = op.ts_std(returns, 20) * cond + p["close"] * (1.0 - cond)
    return op.rank(op.ts_argmax(op.signed_power(x, 2.0), 5)) - 0.5


def f_alpha004(p):  # -1 * ts_rank(rank(low), 9)
    return -1.0 * op.ts_rank(op.rank(p["low"]), 9)


@dataclass
class Factor:
    name: str
    label: str
    category: str
    fn: Callable[[dict], pd.DataFrame]
    description: str
    formula: str = ""

    def compute(self, panel: dict) -> pd.DataFrame:
        return self.fn(panel)


REGISTRY: dict[str, Factor] = {
    "momentum_120": Factor("momentum_120", "6-Month Momentum", "momentum", f_momentum_120,
        "Ranks names by their trailing ~6-month return. Momentum bets that recent winners keep winning.",
        "rank( close_t / close_{t-120} - 1 )"),
    "momentum_252_21": Factor("momentum_252_21", "12m–1m Momentum (Carhart)", "momentum", f_momentum_252_21,
        "The classic academic momentum factor: 12-month return minus the most recent month (which tends to reverse).",
        "zscore( ret_252 - ret_21 )"),
    "reversal_5": Factor("reversal_5", "Short-Term Reversal", "reversal", f_reversal_5,
        "Bets that this week's biggest losers bounce. Over a few days, sharp moves often partly reverse.",
        "rank( -1 * ret_5 )"),
    "low_volatility": Factor("low_volatility", "Low Volatility", "volatility", f_low_volatility,
        "Favors calmer stocks (low recent return volatility). The 'low-vol anomaly' — boring names often hold up well.",
        "rank( -1 * stdev(returns, 20) )"),
    "rsi_oversold": Factor("rsi_oversold", "RSI Oversold", "reversal", f_rsi_oversold,
        "Scores oversold names (low RSI) highest — a mean-reversion idea that dips get bought back.",
        "rank( 50 - RSI_14 )"),
    "volume_surge": Factor("volume_surge", "Volume Surge", "volume", f_volume_surge,
        "Flags names whose recent volume jumped above their baseline — attention/flow often precedes moves.",
        "rank( mean(vol,5) / mean(vol,20) )"),
    "near_high": Factor("near_high", "Near 20-Day High", "momentum", f_near_high,
        "Ranks how close price is to its 20-day high — names breaking out tend to keep running.",
        "rank( close / max(high, 20) )"),
    "alpha101_006": Factor("alpha101_006", "Alpha #6 (open–volume)", "alpha101", f_alpha006,
        "Kakushadze #6: negative correlation of open price and volume over 10 days — an opening price/volume divergence signal.",
        "-1 * correlation(open, volume, 10)"),
    "alpha101_012": Factor("alpha101_012", "Alpha #12 (vol-gated reversal)", "alpha101", f_alpha012,
        "Kakushadze #12: fade the daily price change, gated by whether volume rose — a volume-confirmed reversal.",
        "sign(Δvolume) * (-1 * Δclose)"),
    "alpha101_101": Factor("alpha101_101", "Alpha #101 (intraday push)", "alpha101", f_alpha101,
        "Kakushadze #101: where the close finished within the day's range — an intraday momentum/strength read.",
        "(close - open) / (high - low + .001)"),
    "alpha101_001": Factor("alpha101_001", "Alpha #1 (return/vol momentum)", "alpha101", f_alpha001,
        "Kakushadze #1: time-series momentum that switches to volatility when returns are negative.",
        "rank(ts_argmax(SignedPower(x, 2), 5)) - 0.5"),
    "alpha101_004": Factor("alpha101_004", "Alpha #4 (low reversal)", "alpha101", f_alpha004,
        "Kakushadze #4: a reversal signal on the rank of the day's low over a 9-day window.",
        "-1 * ts_rank(rank(low), 9)"),
}


def get_factor(name: str) -> Factor | None:
    return REGISTRY.get(str(name).lower().strip())


def list_factors() -> list[dict]:
    return [{"name": f.name, "label": f.label, "category": f.category,
             "description": f.description, "formula": f.formula} for f in REGISTRY.values()]
