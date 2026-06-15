"""Alpha operators — the vocabulary factor formulas are written in.

Ported/trimmed from Vibe-Trading's factor base. Every operator acts on a **wide**
DataFrame (index = trading date, columns = instrument) and returns the same shape.
NaN is propagated (no silent fillna); a strict look-ahead ban (delta lag >= 1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _f(df: pd.DataFrame) -> pd.DataFrame:
    return df if df.dtypes.eq(np.float64).all() else df.astype(np.float64)


def rank(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional percentile rank per row (0..1, ties=average)."""
    return df.rank(axis=1, method="average", pct=True, na_option="keep")


def cs_zscore(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score per row: (x - row_mean) / row_std."""
    mean = df.mean(axis=1, skipna=True)
    std = df.std(axis=1, ddof=1, skipna=True)
    out = df.sub(mean, axis=0).div(std.where(std > 0), axis=0)
    return out.replace([np.inf, -np.inf], np.nan)


def scale(df: pd.DataFrame, a: float = 1.0) -> pd.DataFrame:
    """Per-row L1 normalize so the sum of absolute values equals ``a``."""
    df = _f(df)
    abs_sum = df.abs().sum(axis=1, skipna=True).where(lambda s: s > 0)
    return df.mul(a).div(abs_sum, axis=0)


def delta(df: pd.DataFrame, d: int) -> pd.DataFrame:
    """First difference at lag ``d`` (look-ahead ban: d >= 1)."""
    if d < 1:
        raise ValueError(f"delta lag must be >= 1, got {d}")
    return df - df.shift(d)


def ts_mean(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(window=n, min_periods=n).mean()


def ts_std(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(window=n, min_periods=n).std(ddof=1)


def ts_max(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(window=n, min_periods=n).max()


def ts_min(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(window=n, min_periods=n).min()


def ts_corr(x: pd.DataFrame, y: pd.DataFrame, n: int) -> pd.DataFrame:
    """Rolling Pearson correlation per column (constant window -> NaN)."""
    if n < 2:
        raise ValueError(f"ts_corr window must be >= 2, got {n}")
    cols = x.columns.union(y.columns)
    corr = _f(x).reindex(columns=cols).rolling(window=n, min_periods=n).corr(
        _f(y).reindex(columns=cols))
    return corr.replace([np.inf, -np.inf], np.nan)


def _last_rank(arr: np.ndarray) -> float:
    if np.isnan(arr).all():
        return np.nan
    last = arr[-1]
    if np.isnan(last):
        return np.nan
    valid = arr[~np.isnan(arr)]
    if valid.size == 0:
        return np.nan
    less = (valid < last).sum()
    eq = (valid == last).sum()
    return float((less + 0.5 * (eq + 1)) / valid.size)


def ts_rank(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Rolling rank of the last value within the n-window (percentile 0..1)."""
    return df.rolling(window=n, min_periods=n).apply(_last_rank, raw=True)


def _argmax_last(arr: np.ndarray) -> float:
    if np.isnan(arr).all():
        return np.nan
    return float(np.argmax(np.where(np.isnan(arr), -np.inf, arr)))


def ts_argmax(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Rolling argmax (0-based index into the window)."""
    return df.rolling(window=n, min_periods=n).apply(_argmax_last, raw=True)


def signed_power(df: pd.DataFrame, p: float) -> pd.DataFrame:
    """sign(df) * |df|**p — preserves sign, never complex."""
    arr = df.to_numpy(dtype=np.float64, na_value=np.nan)
    return pd.DataFrame(np.sign(arr) * np.power(np.abs(arr), p),
                        index=df.index, columns=df.columns)


def safe_div(a: pd.DataFrame, b: pd.DataFrame, eps: float = 1e-12) -> pd.DataFrame:
    """a / (b + eps*sign(b)); b == 0 -> NaN (never inf/0)."""
    a, b = _f(a), _f(b)
    barr = b.to_numpy(dtype=np.float64, na_value=np.nan)
    denom = pd.DataFrame(barr + eps * np.sign(barr), index=b.index, columns=b.columns)
    return a.div(denom).replace([np.inf, -np.inf], np.nan)
