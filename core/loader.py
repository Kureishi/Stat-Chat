"""Data loading utilities for CSV and Excel files."""

import pandas as pd
from pathlib import Path


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".xlsm"}


def load_file(filepath: str) -> pd.DataFrame:
    """Load a CSV or Excel file into a DataFrame."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}")

    if ext == ".csv":
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    return df


def save_file(df: pd.DataFrame, filepath: str, fmt: str = "csv") -> str:
    """Save a DataFrame to a file in the chosen format."""
    path = Path(filepath)
    fmt = fmt.lower()

    if fmt == "csv":
        out_path = path.with_suffix(".csv")
        df.to_csv(out_path, index=False)
    elif fmt == "xlsx":
        out_path = path.with_suffix(".xlsx")
        df.to_excel(out_path, index=False, engine="openpyxl")
    elif fmt == "json":
        out_path = path.with_suffix(".json")
        df.to_json(out_path, orient="records", indent=2)
    else:
        raise ValueError(f"Unsupported output format: {fmt}")

    return str(out_path)


def get_file_info(df: pd.DataFrame) -> dict:
    """Return basic metadata about a DataFrame."""
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": df.isnull().sum().to_dict(),
        "duplicate_rows": int(df.duplicated().sum()),
        "numeric_columns": list(df.select_dtypes(include="number").columns),
        "categorical_columns": list(df.select_dtypes(exclude="number").columns),
    }
