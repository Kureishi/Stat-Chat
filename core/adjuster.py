"""
core/adjuster.py
----------------
Interprets natural-language adjustment instructions via the configured LLM
backend (Claude API or LM Studio) and applies them to a pandas DataFrame.

Adjustment instructions are translated into a small safe DSL:
  { "op": "add"|"subtract"|"multiply"|"divide"|"set"|"clip"|"round"|
          "rename"|"drop_col"|"filter_rows"|"fillna"|"abs"|"log"|"sqrt",
    "column": "<col>",           # target column (or "*" for all numeric)
    "value":  <number|str>,      # operand (where relevant)
    "condition": "<expr>",       # optional pandas .query() string
    "description": "<human summary>"
  }

Multiple operations are returned as a list.
"""

import json
import math
from typing import Optional
import pandas as pd
import numpy as np

from core.llm_backend import chat_json, get_config, LLMConfig


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """You are a data transformation assistant. The user will describe adjustments
they want to make to a pandas DataFrame in plain English.

You must respond with ONLY a JSON array of operation objects — no prose, no markdown fences.

Each object has these keys:
  op          : one of add | subtract | multiply | divide | set | clip | round |
                rename | drop_col | filter_rows | fillna | abs | log | sqrt
  column      : the column name to operate on (use "*" to mean all numeric columns)
  value       : numeric value, new name string, or clip bounds [min, max]
  condition   : (optional) a pandas DataFrame.query() expression string to limit rows
  description : a short human-readable summary of this operation

Examples:
  User: "Add $1000 to each value in spend"
  -> [{{"op":"add","column":"spend","value":1000,"description":"Add 1000 to spend"}}]

  User: "Multiply income and age by 1.1"
  -> [{{"op":"multiply","column":"income","value":1.1,"description":"Multiply income by 1.1"}},
     {{"op":"multiply","column":"age","value":1.1,"description":"Multiply age by 1.1"}}]

  User: "Rename 'score' to 'risk_score' and drop the 'region' column"
  -> [{{"op":"rename","column":"score","value":"risk_score","description":"Rename score to risk_score"}},
     {{"op":"drop_col","column":"region","description":"Drop column region"}}]

  User: "Clip spend between 0 and 5000"
  -> [{{"op":"clip","column":"spend","value":[0,5000],"description":"Clip spend to [0, 5000]"}}]

  User: "Set all income values below 20000 to 20000"
  -> [{{"op":"clip","column":"income","value":[20000,null],"description":"Floor income at 20000"}}]

  User: "Fill nulls in income with 0"
  -> [{{"op":"fillna","column":"income","value":0,"description":"Fill income nulls with 0"}}]

  User: "Round age to 0 decimal places"
  -> [{{"op":"round","column":"age","value":0,"description":"Round age to 0 decimals"}}]

  User: "Remove rows where spend is negative"
  -> [{{"op":"filter_rows","condition":"spend >= 0","description":"Remove rows where spend < 0"}}]

  User: "Log-transform spend"
  -> [{{"op":"log","column":"spend","description":"Natural log of spend"}}]

Columns available: {columns}
Numeric columns: {numeric_columns}

Only use column names from the list above. Respond with ONLY the JSON array."""


# ── Vision system prompt (for image/PDF annotation workflow) ──────────────────

_VISION_SYSTEM = """You are a data transformation assistant. The user has annotated a
data report (shown as an image) with handwritten notes, highlights, or typed
comments describing changes they want to make to the underlying dataset.

Extract ALL adjustment instructions visible in the image and translate them
into the same JSON operation format.

You must respond with ONLY a JSON array of operation objects — no prose, no markdown fences.

Each object has these keys:
  op          : one of add | subtract | multiply | divide | set | clip | round |
                rename | drop_col | filter_rows | fillna | abs | log | sqrt
  column      : the column name to operate on (use "*" for all numeric columns)
  value       : numeric value, new name string, or clip bounds [min, max]
  condition   : (optional) a pandas .query() expression string
  description : a short human-readable summary of this operation

Columns available: {columns}
Numeric columns: {numeric_columns}

Respond with ONLY the JSON array. If no clear instructions are found, return []."""


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_instructions(instruction: str, df: pd.DataFrame,
                       cfg: Optional[LLMConfig] = None) -> list[dict]:
    """Send a text instruction to the LLM and return operation dicts."""
    columns         = list(df.columns)
    numeric_columns = list(df.select_dtypes(include="number").columns)
    system = _SYSTEM.format(
        columns=json.dumps(columns),
        numeric_columns=json.dumps(numeric_columns),
    )
    return chat_json(system, instruction, cfg=cfg or get_config())


def parse_instructions_from_image(image_b64: str, df: pd.DataFrame,
                                   cfg: Optional[LLMConfig] = None) -> list[dict]:
    """
    Send an annotated report image to a vision LLM and return operation dicts.

    image_b64 : base64-encoded PNG or JPEG of the annotated report page.
    df        : current DataFrame (used for column hints in the system prompt).
    """
    columns         = list(df.columns)
    numeric_columns = list(df.select_dtypes(include="number").columns)
    system = _VISION_SYSTEM.format(
        columns=json.dumps(columns),
        numeric_columns=json.dumps(numeric_columns),
    )
    vision_cfg = cfg or get_config()
    # If the global config is text-only lmstudio, auto-switch to vision variant
    if vision_cfg.provider == "lmstudio":
        from dataclasses import replace
        vision_cfg = replace(vision_cfg, provider="lmstudio_vision")

    return chat_json(system, "Please extract all adjustment instructions from this annotated report.",
                     image_b64=image_b64, cfg=vision_cfg)


# ── Operation executor ────────────────────────────────────────────────────────

def _resolve_mask(df: pd.DataFrame, condition: Optional[str]) -> pd.Series:
    if not condition:
        return pd.Series([True] * len(df), index=df.index)
    return df.eval(condition)


def apply_operation(df: pd.DataFrame, op: dict) -> tuple[pd.DataFrame, str]:
    """Apply a single operation dict to df. Returns (new_df, description)."""
    df      = df.copy()
    o       = op.get("op", "").lower()
    col     = op.get("column", "")
    val     = op.get("value")
    cond    = op.get("condition")
    desc    = op.get("description", f"{o} on {col}")
    numeric = list(df.select_dtypes(include="number").columns)

    target_cols = numeric if col == "*" else [col]
    for tc in target_cols:
        if tc not in df.columns and o not in ("filter_rows", "rename"):
            raise ValueError(f"Column '{tc}' not found in dataset.")

    mask = _resolve_mask(df, cond)

    if o == "add":
        for tc in target_cols:
            df.loc[mask, tc] = df.loc[mask, tc] + float(val)

    elif o == "subtract":
        for tc in target_cols:
            df.loc[mask, tc] = df.loc[mask, tc] - float(val)

    elif o == "multiply":
        for tc in target_cols:
            df.loc[mask, tc] = df.loc[mask, tc] * float(val)

    elif o == "divide":
        if float(val) == 0:
            raise ValueError("Division by zero.")
        for tc in target_cols:
            df.loc[mask, tc] = df.loc[mask, tc] / float(val)

    elif o == "set":
        for tc in target_cols:
            df.loc[mask, tc] = float(val) if isinstance(val, (int, float)) else val

    elif o == "clip":
        lo, hi = (val[0], val[1]) if isinstance(val, list) else (None, None)
        lo = None if lo is None or (isinstance(lo, float) and math.isnan(lo)) else float(lo)
        hi = None if hi is None or (isinstance(hi, float) and math.isnan(hi)) else float(hi)
        for tc in target_cols:
            df[tc] = df[tc].clip(lower=lo, upper=hi)

    elif o == "round":
        decimals = int(val) if val is not None else 0
        for tc in target_cols:
            df[tc] = df[tc].round(decimals)

    elif o == "rename":
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found.")
        df = df.rename(columns={col: str(val)})

    elif o == "drop_col":
        for tc in target_cols:
            df = df.drop(columns=[tc], errors="ignore")

    elif o == "filter_rows":
        if not cond:
            raise ValueError("filter_rows requires a condition.")
        df = df.query(cond).reset_index(drop=True)

    elif o == "fillna":
        for tc in target_cols:
            df[tc] = df[tc].fillna(float(val) if isinstance(val, (int, float)) else val)

    elif o == "abs":
        for tc in target_cols:
            df[tc] = df[tc].abs()

    elif o == "log":
        for tc in target_cols:
            df[tc] = np.log(df[tc].replace(0, np.nan))

    elif o == "sqrt":
        for tc in target_cols:
            df[tc] = np.sqrt(df[tc].clip(lower=0))

    else:
        raise ValueError(f"Unknown operation: '{o}'")

    return df, desc


def apply_instructions(df: pd.DataFrame, instruction: str,
                       cfg: Optional[LLMConfig] = None) -> tuple[pd.DataFrame, list[str], list[dict]]:
    """
    Parse and apply all operations from a natural-language instruction.
    Returns (modified_df, descriptions_list, ops_list).
    """
    ops = parse_instructions(instruction, df, cfg=cfg)
    descriptions = []
    for op in ops:
        df, desc = apply_operation(df, op)
        descriptions.append(desc)
    return df, descriptions, ops


def apply_instructions_from_image(df: pd.DataFrame, image_b64: str,
                                   cfg: Optional[LLMConfig] = None
                                   ) -> tuple[pd.DataFrame, list[str], list[dict]]:
    """
    Parse and apply operations extracted from an annotated report image.
    Returns (modified_df, descriptions_list, ops_list).
    """
    ops = parse_instructions_from_image(image_b64, df, cfg=cfg)
    if not ops:
        raise ValueError("No adjustment instructions found in the image.")
    descriptions = []
    for op in ops:
        df, desc = apply_operation(df, op)
        descriptions.append(desc)
    return df, descriptions, ops
