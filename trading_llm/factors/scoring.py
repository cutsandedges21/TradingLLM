"""IC/IR benchmarking — does a factor's ranking predict forward returns?

IC (Information Coefficient) = the cross-sectional Spearman rank correlation, each
day, between a factor's values and the *next* few days' returns. Average it over
time for IC mean; IR = IC mean / IC std (consistency). Ported from Vibe-Trading's
``compute_ic_series``; the spread + classification are ours.
"""
from __future__ import annotations

import math

import pandas as pd

_MIN_VALID_PER_DATE = 5


def forward_returns(close: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """Return from each date t to t+horizon (NaN at the tail). No look-ahead: the
    factor at t is correlated with the return earned *after* t."""
    fwd = close.shift(-horizon) / close - 1.0
    return fwd


def compute_ic_series(factor_df: pd.DataFrame, return_df: pd.DataFrame) -> pd.Series:
    """Daily Spearman IC between factor values and forward returns."""
    dates = factor_df.index.intersection(return_df.index)
    codes = factor_df.columns.intersection(return_df.columns)
    if len(dates) == 0 or len(codes) == 0:
        return pd.Series(dtype=float)
    f = factor_df.loc[dates, codes]
    r = return_df.loc[dates, codes]
    mask = f.notna() & r.notna()
    n_valid = mask.sum(axis=1)
    fr = f.where(mask).rank(axis=1, method="average")
    rr = r.where(mask).rank(axis=1, method="average")
    ic = fr.corrwith(rr, axis=1, method="pearson")
    ic = ic[n_valid >= _MIN_VALID_PER_DATE].dropna()
    return ic.astype(float) if not ic.empty else pd.Series(dtype=float)


def quantile_spread(factor_df: pd.DataFrame, return_df: pd.DataFrame,
                    q: float = 0.3) -> float:
    """Average forward-return gap between the top and bottom factor quantile (%).

    A simple, intuitive read: "top-ranked names beat bottom-ranked by X% over the
    horizon, on average." Uses the top/bottom ``q`` fraction each date.
    """
    dates = factor_df.index.intersection(return_df.index)
    codes = factor_df.columns.intersection(return_df.columns)
    if len(dates) == 0 or len(codes) == 0:
        return 0.0
    f = factor_df.loc[dates, codes]
    r = return_df.loc[dates, codes]
    spreads = []
    for d in dates:
        fv = f.loc[d].dropna()
        rv = r.loc[d].dropna()
        shared = fv.index.intersection(rv.index)
        if len(shared) < _MIN_VALID_PER_DATE:
            continue
        fv, rv = fv[shared], rv[shared]
        k = max(1, int(len(shared) * q))
        order = fv.sort_values()
        bottom = rv[order.index[:k]].mean()
        top = rv[order.index[-k:]].mean()
        spreads.append(top - bottom)
    if not spreads:
        return 0.0
    return float(pd.Series(spreads).mean() * 100)


def classify(ic_mean: float, ir: float) -> tuple[str, str]:
    """(strength, direction) labels for a factor's IC."""
    a = abs(ic_mean)
    if a >= 0.03 and abs(ir) >= 0.3:
        strength = "strong"
    elif a >= 0.015:
        strength = "alive"
    else:
        strength = "weak"
    direction = "momentum" if ic_mean > 0 else "reversal"
    return strength, direction


def ic_stats(ic: pd.Series) -> dict:
    n = int(len(ic))
    if n < 2:
        return {"ic_mean": 0.0, "ic_std": 0.0, "ir": 0.0, "t_stat": 0.0,
                "ic_positive_pct": 0.0, "n_days": n}
    mean = float(ic.mean())
    std = float(ic.std(ddof=1))
    ir = mean / std if std > 0 else 0.0
    t_stat = mean / std * math.sqrt(n) if std > 0 else 0.0
    return {
        "ic_mean": round(mean, 4),
        "ic_std": round(std, 4),
        "ir": round(ir, 3),
        "t_stat": round(t_stat, 2),
        "ic_positive_pct": round(float((ic > 0).mean()) * 100, 1),
        "n_days": n,
    }
