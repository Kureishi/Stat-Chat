"""Data cleaning and normalization utilities."""

import pandas as pd
import numpy as np
from typing import Optional, List


# ── Cleaning ──────────────────────────────────────────────────────────────────

def drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    return df, removed


def drop_null_rows(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.dropna()
    removed = before - len(df)
    return df, removed


def fill_nulls(df: pd.DataFrame, strategy: str = "mean",
               columns: Optional[List[str]] = None) -> pd.DataFrame:
    """Fill missing values.

    strategy: 'mean' | 'median' | 'mode' | 'zero'
    columns : list of columns to fill; None = all numeric (mean/median/zero) or all (mode)
    """
    df = df.copy()
    numeric_cols = list(df.select_dtypes(include="number").columns)
    target_cols = columns if columns else numeric_cols

    if strategy == "mean":
        for col in target_cols:
            if col in numeric_cols:
                df[col] = df[col].fillna(df[col].mean())
    elif strategy == "median":
        for col in target_cols:
            if col in numeric_cols:
                df[col] = df[col].fillna(df[col].median())
    elif strategy == "mode":
        for col in (columns if columns else df.columns):
            mode_val = df[col].mode()
            if not mode_val.empty:
                df[col] = df[col].fillna(mode_val[0])
    elif strategy == "zero":
        for col in target_cols:
            if col in numeric_cols:
                df[col] = df[col].fillna(0)
    else:
        raise ValueError(f"Unknown fill strategy: {strategy}")

    return df


# ── Normalization ─────────────────────────────────────────────────────────────

def normalize_zscore(df: pd.DataFrame, columns: Optional[List[str]] = None,
                     target_mean: float = 0.0, target_std: float = 1.0) -> pd.DataFrame:
    """Z-score normalization, optionally scaled to target mean/std."""
    df = df.copy()
    cols = columns if columns else list(df.select_dtypes(include="number").columns)
    for col in cols:
        mu = df[col].mean()
        sigma = df[col].std()
        if sigma != 0:
            df[col] = ((df[col] - mu) / sigma) * target_std + target_mean
        else:
            df[col] = target_mean
    return df


def normalize_minmax(df: pd.DataFrame, columns: Optional[List[str]] = None,
                     feature_range: tuple = (0, 1)) -> pd.DataFrame:
    """Min-max scaling to [feature_range[0], feature_range[1]]."""
    df = df.copy()
    cols = columns if columns else list(df.select_dtypes(include="number").columns)
    lo, hi = feature_range
    for col in cols:
        mn = df[col].min()
        mx = df[col].max()
        rng = mx - mn
        if rng != 0:
            df[col] = (df[col] - mn) / rng * (hi - lo) + lo
        else:
            df[col] = lo
    return df


def normalize_robust(df: pd.DataFrame, columns: Optional[List[str]] = None) -> pd.DataFrame:
    """Robust scaling using median and IQR (resistant to outliers)."""
    df = df.copy()
    cols = columns if columns else list(df.select_dtypes(include="number").columns)
    for col in cols:
        med = df[col].median()
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        if iqr != 0:
            df[col] = (df[col] - med) / iqr
        else:
            df[col] = 0.0
    return df


def apply_cleaning(df: pd.DataFrame, opts: dict) -> tuple[pd.DataFrame, list]:
    """Apply all selected cleaning operations. Returns (cleaned_df, log_messages)."""
    log = []
    if opts.get("drop_duplicates"):
        df, n = drop_duplicates(df)
        log.append(f"Removed {n} duplicate row(s).")
    if opts.get("drop_nulls"):
        df, n = drop_null_rows(df)
        log.append(f"Dropped {n} row(s) with null values.")
    if opts.get("fill_nulls"):
        strategy = opts["fill_nulls"]
        df = fill_nulls(df, strategy=strategy)
        log.append(f"Filled missing values using '{strategy}' strategy.")
    return df, log


def apply_normalization(df: pd.DataFrame, opts: dict) -> tuple[pd.DataFrame, list]:
    """Apply normalization. Returns (normalized_df, log_messages)."""
    log = []
    method = opts.get("normalize")
    if not method:
        return df, log
    cols = opts.get("norm_columns") or None
    if method == "zscore":
        mu = opts.get("norm_mean", 0.0)
        std = opts.get("norm_std", 1.0)
        df = normalize_zscore(df, columns=cols, target_mean=mu, target_std=std)
        log.append(f"Z-score normalization applied (target mean={mu}, std={std}).")
    elif method == "minmax":
        df = normalize_minmax(df, columns=cols)
        log.append("Min-Max normalization applied (range [0, 1]).")
    elif method == "robust":
        df = normalize_robust(df, columns=cols)
        log.append("Robust normalization applied (median/IQR).")
    return df, log
