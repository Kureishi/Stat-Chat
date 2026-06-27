"""PDF report generation using ReportLab."""

import io
import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)


# ── Colour palette ─────────────────────────────────────────────────────────────
PRIMARY   = colors.HexColor("#2563EB")   # blue-600
SECONDARY = colors.HexColor("#0F172A")   # slate-900
ACCENT    = colors.HexColor("#7C3AED")   # violet-600
SUCCESS   = colors.HexColor("#059669")   # emerald-600
WARNING   = colors.HexColor("#D97706")   # amber-600
DANGER    = colors.HexColor("#DC2626")   # red-600
BG_LIGHT  = colors.HexColor("#F1F5F9")   # slate-100
BG_HEADER = colors.HexColor("#1E3A5F")   # deep navy
GREY_MID  = colors.HexColor("#94A3B8")   # slate-400
GREY_BORDER = colors.HexColor("#CBD5E1") # slate-300


def _styles():
    base = getSampleStyleSheet()
    custom = {
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"],
            fontSize=26, textColor=colors.white,
            spaceAfter=4, fontName="Helvetica-Bold", alignment=TA_CENTER
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"],
            fontSize=11, textColor=colors.HexColor("#CBD5E1"),
            spaceAfter=6, alignment=TA_CENTER
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"],
            fontSize=15, textColor=BG_HEADER,
            spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold",
            borderPad=4
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"],
            fontSize=12, textColor=SECONDARY,
            spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold"
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"],
            fontSize=9.5, textColor=SECONDARY, leading=15
        ),
        "small": ParagraphStyle(
            "Small", parent=base["Normal"],
            fontSize=8, textColor=GREY_MID, leading=12
        ),
        "code": ParagraphStyle(
            "Code", parent=base["Code"],
            fontSize=8, textColor=colors.HexColor("#1E40AF"),
            backColor=BG_LIGHT, borderPad=4
        ),
        "note": ParagraphStyle(
            "Note", parent=base["Normal"],
            fontSize=8.5, textColor=WARNING,
            leftIndent=10, leading=13
        ),
    }
    return custom


def _section_rule(story, styles):
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceAfter=10))


def _kv_table(data: list[tuple], col_widths=None):
    """Small key-value table with alternating rows."""
    col_widths = col_widths or [2.4 * inch, 4 * inch]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME",   (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",  (0, 0), (0, -1),  PRIMARY),
        ("TEXTCOLOR",  (1, 0), (1, -1),  SECONDARY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, BG_LIGHT]),
        ("GRID",       (0, 0), (-1, -1), 0.5, GREY_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _df_table(df: pd.DataFrame, max_rows: int = 20, title: str = ""):
    """Render a DataFrame as a styled table."""
    df_display = df.head(max_rows)
    headers = list(df_display.columns)
    data = [headers] + [[str(round(v, 4)) if isinstance(v, float) else str(v)
                          for v in row] for row in df_display.values]
    n_cols = len(headers)
    col_w = min(1.2 * inch, 6.5 * inch / max(n_cols, 1))
    col_widths = [col_w] * n_cols

    t = Table(data, colWidths=col_widths, repeatRows=1)
    ts = TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  BG_HEADER),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("GRID",        (0, 0), (-1, -1), 0.4, GREY_BORDER),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
    ])
    t.setStyle(ts)
    return t


def _corr_heatmap_image(corr_df: pd.DataFrame) -> io.BytesIO:
    n = len(corr_df)
    fig_size = max(4, min(n * 0.7, 8))
    fig, ax = plt.subplots(figsize=(fig_size, fig_size * 0.85))
    cmap = plt.cm.RdBu_r
    im = ax.imshow(corr_df.values, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(corr_df.columns, rotation=45, ha="right", fontsize=7)
    ax.set_yticklabels(corr_df.index, fontsize=7)
    for i in range(n):
        for j in range(n):
            val = corr_df.iloc[i, j]
            color = "white" if abs(val) > 0.6 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=6, color=color)
    plt.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title("Correlation Matrix", fontsize=10, fontweight="bold", pad=10)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _roc_curve_image(roc_data: dict) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(5, 4))
    cmap_colors = plt.cm.tab10.colors
    for i, (col, vals) in enumerate(roc_data.items()):
        if "error" in vals:
            continue
        color = cmap_colors[i % len(cmap_colors)]
        ax.plot(vals["fpr"], vals["tpr"],
                label=f"{col} (AUC={vals['auc']:.3f})", color=color, lw=1.8)
    ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5, label="Random")
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1.02])
    ax.set_xlabel("False Positive Rate", fontsize=9)
    ax.set_ylabel("True Positive Rate", fontsize=9)
    ax.set_title("ROC Curves", fontsize=10, fontweight="bold")
    ax.legend(fontsize=7, loc="lower right")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _dist_plots_image(df: pd.DataFrame, max_cols: int = 6) -> io.BytesIO:
    num_cols = list(df.select_dtypes(include="number").columns)[:max_cols]
    n = len(num_cols)
    if n == 0:
        return None
    cols_grid = min(3, n)
    rows_grid = (n + cols_grid - 1) // cols_grid
    fig, axes = plt.subplots(rows_grid, cols_grid,
                              figsize=(cols_grid * 3, rows_grid * 2.5))
    axes = np.array(axes).flatten() if n > 1 else [axes]
    for i, col in enumerate(num_cols):
        ax = axes[i]
        data = df[col].dropna()
        ax.hist(data, bins=30, color="#2563EB", alpha=0.75, edgecolor="white", linewidth=0.4)
        ax.axvline(data.mean(), color="#DC2626", lw=1.5, linestyle="--", label="mean")
        ax.axvline(data.median(), color="#059669", lw=1.5, linestyle=":", label="median")
        ax.set_title(col, fontsize=8, fontweight="bold")
        ax.set_xlabel("Value", fontsize=7)
        ax.set_ylabel("Count", fontsize=7)
        ax.tick_params(labelsize=6)
        ax.legend(fontsize=6)
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)
    plt.suptitle("Feature Distributions", fontsize=10, fontweight="bold", y=1.01)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Main report builder ────────────────────────────────────────────────────────

def generate_report(
    filepath: str,
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    analysis_results: Dict[str, Any],
    clean_log: list,
    norm_log: list,
    source_file: str = "",
) -> str:
    """Generate a PDF report and save to filepath. Returns the output path."""
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    S = _styles()
    story = []
    now = datetime.datetime.now().strftime("%B %d, %Y  %H:%M")

    # ── Cover block ───────────────────────────────────────────────────────────
    cover_data = [[
        Paragraph("<b>DataLyzer</b>", S["title"]),
    ]]
    cover_table = Table(cover_data, colWidths=[6.5 * inch])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_HEADER),
        ("TOPPADDING", (0, 0), (-1, -1), 22),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("ROUNDEDCORNERS", [6], ),
    ]))
    story.append(cover_table)
    story.append(Paragraph("Statistical Analysis Report", S["subtitle"]))
    story.append(Paragraph(f"Generated: {now}", S["small"]))
    if source_file:
        story.append(Paragraph(f"Source: {Path(source_file).name}", S["small"]))
    story.append(Spacer(1, 16))

    # ── Dataset overview ──────────────────────────────────────────────────────
    story.append(Paragraph("1. Dataset Overview", S["h1"]))
    _section_rule(story, S)
    num_cols = list(cleaned_df.select_dtypes(include="number").columns)
    cat_cols = list(cleaned_df.select_dtypes(exclude="number").columns)
    missing = int(cleaned_df.isnull().sum().sum())
    kv = [
        ("Original rows",    str(len(original_df))),
        ("Processed rows",   str(len(cleaned_df))),
        ("Rows removed",     str(len(original_df) - len(cleaned_df))),
        ("Columns",          str(len(cleaned_df.columns))),
        ("Numeric columns",  str(len(num_cols))),
        ("Categorical cols", str(len(cat_cols))),
        ("Missing values (post-clean)", str(missing)),
    ]
    story.append(_kv_table(kv))
    story.append(Spacer(1, 10))

    # Column list
    if num_cols:
        story.append(Paragraph("Numeric columns: " + ", ".join(num_cols), S["small"]))
    if cat_cols:
        story.append(Paragraph("Categorical columns: " + ", ".join(cat_cols), S["small"]))
    story.append(Spacer(1, 10))

    # ── Preprocessing log ─────────────────────────────────────────────────────
    if clean_log or norm_log:
        story.append(Paragraph("2. Preprocessing Steps", S["h1"]))
        _section_rule(story, S)
        for msg in clean_log + norm_log:
            story.append(Paragraph(f"• {msg}", S["body"]))
        story.append(Spacer(1, 10))

    # ── Data preview ──────────────────────────────────────────────────────────
    story.append(Paragraph("3. Data Preview (first 10 rows)", S["h1"]))
    _section_rule(story, S)
    story.append(_df_table(cleaned_df, max_rows=10))
    story.append(Spacer(1, 12))

    # ── Distribution plots ────────────────────────────────────────────────────
    if num_cols:
        buf = _dist_plots_image(cleaned_df)
        if buf:
            story.append(Paragraph("4. Feature Distributions", S["h1"]))
            _section_rule(story, S)
            img = Image(buf, width=6.5 * inch, height=4 * inch)
            story.append(img)
            story.append(Spacer(1, 12))

    sec = 5  # running section counter

    # ── Central tendency ──────────────────────────────────────────────────────
    if "central_tendency" in analysis_results:
        story.append(Paragraph(f"{sec}. Measures of Central Tendency", S["h1"]))
        _section_rule(story, S)
        sec += 1
        ct = analysis_results["central_tendency"]
        header = ["Column", "Mean", "Median", "Mode", "N"]
        data = [header]
        for col, v in ct.items():
            data.append([
                col,
                f"{v['mean']:.4f}",
                f"{v['median']:.4f}",
                f"{v['mode']:.4f}" if v['mode'] is not None else "—",
                str(v['n']),
            ])
        t = Table(data, colWidths=[2 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch, 0.8 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  BG_HEADER),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ("GRID",        (0, 0), (-1, -1), 0.4, GREY_BORDER),
            ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    # ── Dispersion ────────────────────────────────────────────────────────────
    if "dispersion" in analysis_results:
        story.append(Paragraph(f"{sec}. Measures of Dispersion", S["h1"]))
        _section_rule(story, S)
        sec += 1
        disp = analysis_results["dispersion"]
        header = ["Column", "Std Dev", "Variance", "Range", "IQR", "Min", "Max"]
        data = [header]
        for col, v in disp.items():
            data.append([
                col,
                f"{v['std_dev']:.4f}",
                f"{v['variance']:.4f}",
                f"{v['range']:.4f}",
                f"{v['iqr']:.4f}",
                f"{v['min']:.4f}",
                f"{v['max']:.4f}",
            ])
        t = Table(data, colWidths=[1.7 * inch, 1 * inch, 1 * inch, 0.9 * inch, 0.8 * inch, 0.9 * inch, 0.9 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  BG_HEADER),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ("GRID",        (0, 0), (-1, -1), 0.4, GREY_BORDER),
            ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    # ── Shape stats ───────────────────────────────────────────────────────────
    if "shape" in analysis_results:
        story.append(Paragraph(f"{sec}. Distribution Shape (Skewness & Kurtosis)", S["h1"]))
        _section_rule(story, S)
        sec += 1
        sh = analysis_results["shape"]
        header = ["Column", "Skewness", "Kurtosis", "Skew Interpretation"]
        data = [header]
        for col, v in sh.items():
            sk = v["skewness"]
            interp = "Symmetric" if abs(sk) < 0.5 else ("Moderate skew" if abs(sk) < 1 else "High skew")
            interp += " (left)" if sk < 0 else " (right)" if sk > 0 else ""
            data.append([col, f"{sk:.4f}", f"{v['kurtosis']:.4f}", interp])
        t = Table(data, colWidths=[1.8 * inch, 1.1 * inch, 1.1 * inch, 2.5 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  BG_HEADER),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ("GRID",        (0, 0), (-1, -1), 0.4, GREY_BORDER),
            ("ALIGN",       (1, 0), (2, -1),  "CENTER"),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    # ── Percentiles ───────────────────────────────────────────────────────────
    if "percentiles" in analysis_results:
        story.append(Paragraph(f"{sec}. Percentile Statistics", S["h1"]))
        _section_rule(story, S)
        sec += 1
        pct = analysis_results["percentiles"]
        header = ["Column", "P5", "P10", "P25", "P50", "P75", "P90", "P95"]
        data = [header]
        for col, v in pct.items():
            data.append([col] + [f"{v[k]:.4f}" for k in ["p5","p10","p25","p50","p75","p90","p95"]])
        cw = [1.8 * inch] + [0.7 * inch] * 7
        t = Table(data, colWidths=cw)
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  BG_HEADER),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ("GRID",        (0, 0), (-1, -1), 0.4, GREY_BORDER),
            ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    # ── Normality ─────────────────────────────────────────────────────────────
    if "normality" in analysis_results:
        story.append(Paragraph(f"{sec}. Normality Tests (Shapiro-Wilk)", S["h1"]))
        _section_rule(story, S)
        sec += 1
        nrm = analysis_results["normality"]
        header = ["Column", "Statistic", "p-value", "Normal (p>0.05)?"]
        data = [header]
        for col, v in nrm.items():
            if "note" in v:
                data.append([col, "—", "—", v["note"]])
            else:
                data.append([
                    col,
                    f"{v['statistic']:.4f}",
                    f"{v['p_value']:.4f}",
                    "Yes" if v["is_normal"] else "No",
                ])
        t = Table(data, colWidths=[2.0 * inch, 1.2 * inch, 1.2 * inch, 2.0 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  BG_HEADER),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ("GRID",        (0, 0), (-1, -1), 0.4, GREY_BORDER),
            ("ALIGN",       (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",  (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    # ── Correlation ───────────────────────────────────────────────────────────
    if "correlation" in analysis_results:
        story.append(Paragraph(f"{sec}. Correlation Matrix", S["h1"]))
        _section_rule(story, S)
        sec += 1
        corr_df = analysis_results["correlation"]
        if isinstance(corr_df, pd.DataFrame) and len(corr_df) > 1:
            buf = _corr_heatmap_image(corr_df)
            w = min(6.5 * inch, len(corr_df) * 0.9 * inch + 1 * inch)
            img = Image(buf, width=w, height=w * 0.8)
            story.append(img)
        story.append(Spacer(1, 12))

    # ── ROC-AUC ───────────────────────────────────────────────────────────────
    if "roc_auc" in analysis_results:
        story.append(Paragraph(f"{sec}. ROC-AUC Analysis", S["h1"]))
        _section_rule(story, S)
        sec += 1
        roc = analysis_results["roc_auc"]
        if "error" in roc:
            story.append(Paragraph(f"Error: {roc['error']}", S["note"]))
        else:
            # AUC summary table
            header = ["Feature", "AUC Score", "Interpretation"]
            data = [header]
            for col, v in roc.items():
                if "error" in v:
                    data.append([col, "Error", v["error"]])
                else:
                    auc = v["auc"]
                    interp = ("Poor (<0.6)" if auc < 0.6
                              else "Fair" if auc < 0.7
                              else "Good" if auc < 0.8
                              else "Very Good" if auc < 0.9
                              else "Excellent (>=0.9)")
                    data.append([col, f"{auc:.4f}", interp])
            t = Table(data, colWidths=[2.5 * inch, 1.5 * inch, 2.5 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0),  BG_HEADER),
                ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
                ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
                ("GRID",        (0, 0), (-1, -1), 0.4, GREY_BORDER),
                ("ALIGN",       (1, 0), (1, -1),  "CENTER"),
                ("TOPPADDING",  (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))
            # ROC curve plot
            buf = _roc_curve_image(roc)
            img = Image(buf, width=5 * inch, height=4 * inch)
            story.append(img)
        story.append(Spacer(1, 12))

    # ── Footer note ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY_BORDER))
    story.append(Paragraph(
        "Report generated by DataLyzer · All statistics computed on cleaned/normalized data.",
        S["small"]
    ))

    doc.build(story)
    return filepath
