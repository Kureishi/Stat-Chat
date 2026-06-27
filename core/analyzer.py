"""Statistical analysis routines."""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Optional, List, Dict, Any


def central_tendency(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    cols = columns or list(df.select_dtypes(include="number").columns)
    result = {}
    for col in cols:
        s = df[col].dropna()
        mode_vals = s.mode()
        result[col] = {
            "mean": float(s.mean()),
            "median": float(s.median()),
            "mode": float(mode_vals.iloc[0]) if not mode_vals.empty else None,
            "n": int(s.count()),
        }
    return result


def dispersion(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    cols = columns or list(df.select_dtypes(include="number").columns)
    result = {}
    for col in cols:
        s = df[col].dropna()
        q1 = float(s.quantile(0.25))
        q3 = float(s.quantile(0.75))
        result[col] = {
            "variance": float(s.var()),
            "std_dev": float(s.std()),
            "range": float(s.max() - s.min()),
            "iqr": float(q3 - q1),
            "min": float(s.min()),
            "max": float(s.max()),
            "cv": float(s.std() / s.mean() * 100) if s.mean() != 0 else None,
        }
    return result


def shape_stats(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    cols = columns or list(df.select_dtypes(include="number").columns)
    result = {}
    for col in cols:
        s = df[col].dropna()
        result[col] = {
            "skewness": float(s.skew()),
            "kurtosis": float(s.kurtosis()),
        }
    return result


def percentile_stats(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    cols = columns or list(df.select_dtypes(include="number").columns)
    levels = [5, 10, 25, 50, 75, 90, 95]
    result = {}
    for col in cols:
        s = df[col].dropna()
        result[col] = {f"p{p}": float(s.quantile(p / 100)) for p in levels}
    return result


def correlation_matrix(df: pd.DataFrame, columns: Optional[List[str]] = None) -> pd.DataFrame:
    cols = columns or list(df.select_dtypes(include="number").columns)
    return df[cols].corr()


def roc_auc_analysis(df: pd.DataFrame, target_col: str,
                     feature_cols: Optional[List[str]] = None,
                     original_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Compute ROC-AUC for each numeric feature vs a binary target column.

    original_df: if provided, the target labels are taken from here (pre-normalization).
    """
    from sklearn.metrics import roc_auc_score, roc_curve

    label_source = original_df if original_df is not None else df

    if target_col not in label_source.columns:
        raise ValueError(f"Target column '{target_col}' not found in data.")

    y_check = label_source[target_col].dropna()
    unique_vals = y_check.unique()
    if len(unique_vals) != 2:
        raise ValueError(
            f"ROC-AUC requires a binary target. Column '{target_col}' has {len(unique_vals)} unique values: {list(unique_vals)[:5]}"
        )

    numeric_cols = feature_cols or [
        c for c in df.select_dtypes(include="number").columns if c != target_col
    ]

    results = {}
    # Try to get labels from the cleaned df itself first (if target wasn't normalized)
    # Otherwise fall back to aligning by reset index
    for col in numeric_cols:
        try:
            if target_col in df.columns:
                valid = df[[col, target_col]].dropna()
                y_true = valid[target_col]
                y_score = valid[col]
            else:
                min_len = min(len(df), len(label_source))
                y_true = label_source[target_col].iloc[:min_len].reset_index(drop=True)
                y_score = df[col].iloc[:min_len].reset_index(drop=True)
                mask = y_true.notna() & y_score.notna()
                y_true, y_score = y_true[mask], y_score[mask]

            if len(y_true) < 2:
                continue
            auc = roc_auc_score(y_true, y_score)
            fpr, tpr, thresholds = roc_curve(y_true, y_score)
            results[col] = {
                "auc": float(auc),
                "fpr": fpr.tolist(),
                "tpr": tpr.tolist(),
                "thresholds": thresholds.tolist(),
            }
        except Exception as e:
            results[col] = {"error": str(e)}
    return results


def normality_tests(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    """Shapiro-Wilk normality test for each column."""
    cols = columns or list(df.select_dtypes(include="number").columns)
    result = {}
    for col in cols:
        s = df[col].dropna()
        if len(s) < 3:
            result[col] = {"note": "Not enough data"}
            continue
        sample = s if len(s) <= 5000 else s.sample(5000, random_state=42)
        stat, p = stats.shapiro(sample)
        result[col] = {
            "statistic": float(stat),
            "p_value": float(p),
            "is_normal": bool(p > 0.05),
        }
    return result


def run_analysis(df: pd.DataFrame, opts: dict) -> Dict[str, Any]:
    """Run all selected analyses. opts keys map to booleans or special values."""
    results = {}
    numeric_cols = list(df.select_dtypes(include="number").columns)

    if not numeric_cols:
        return {"error": "No numeric columns found for analysis."}

    all_metrics = opts.get("all_metrics", False)

    if all_metrics or opts.get("central_tendency"):
        results["central_tendency"] = central_tendency(df)

    if all_metrics or opts.get("dispersion"):
        results["dispersion"] = dispersion(df)

    if all_metrics or opts.get("shape"):
        results["shape"] = shape_stats(df)

    if all_metrics or opts.get("percentiles"):
        results["percentiles"] = percentile_stats(df)

    if all_metrics or opts.get("correlation"):
        results["correlation"] = correlation_matrix(df)

    if all_metrics or opts.get("normality"):
        results["normality"] = normality_tests(df)

    if opts.get("roc_auc"):
        target = opts["roc_auc"]
        original_df = opts.get("original_df")
        try:
            results["roc_auc"] = roc_auc_analysis(df, target_col=target, original_df=original_df)
        except ValueError as e:
            results["roc_auc"] = {"error": str(e)}

    return results
