"""
Stat Chat GUI — Tkinter-based interface for data cleaning, normalization,
statistical analysis, and iterative AI-powered dataset adjustment.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.loader import load_file, save_file, get_file_info
from core.cleaner import apply_cleaning, apply_normalization
from core.analyzer import run_analysis
from core.llm_backend import get_config, set_config, LLMConfig
from gui.chat_panel import AdjustPanel

# ── Colour tokens ──────────────────────────────────────────────────────────────
C = {
    "bg":        "#0F172A",
    "panel":     "#1E293B",
    "card":      "#1E3A5F",
    "border":    "#334155",
    "primary":   "#2563EB",
    "primary_h": "#1D4ED8",
    "accent":    "#7C3AED",
    "success":   "#059669",
    "warning":   "#D97706",
    "danger":    "#DC2626",
    "text":      "#F1F5F9",
    "muted":     "#94A3B8",
    "highlight": "#0EA5E9",
}

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_H2    = ("Segoe UI", 12, "bold")
FONT_LABEL = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 9)
FONT_BTN   = ("Segoe UI", 10, "bold")


# ── Reusable widgets ───────────────────────────────────────────────────────────

class StyledButton(tk.Button):
    def __init__(self, parent, text, command=None, color=None, **kwargs):
        color = color or C["primary"]
        super().__init__(
            parent, text=text, command=command,
            bg=color, fg=C["text"], activebackground=C["primary_h"],
            activeforeground=C["text"],
            relief="flat", bd=0, padx=14, pady=6,
            font=FONT_BTN, cursor="hand2", **kwargs
        )
        self._color = color
        self.bind("<Enter>", lambda e: self.config(bg=self._dk()))
        self.bind("<Leave>", lambda e: self.config(bg=color))

    def _dk(self):
        r, g, b = int(self._color[1:3],16), int(self._color[3:5],16), int(self._color[5:7],16)
        return "#{:02x}{:02x}{:02x}".format(max(0,r-30), max(0,g-30), max(0,b-30))


class SectionLabel(tk.Label):
    def __init__(self, parent, text, **kwargs):
        super().__init__(parent, text=text, font=FONT_H2,
                         bg=C["panel"], fg=C["highlight"],
                         anchor="w", pady=6, **kwargs)


class CheckRow(tk.Frame):
    def __init__(self, parent, label, var, **kwargs):
        super().__init__(parent, bg=C["panel"], **kwargs)
        self.var = var
        tk.Checkbutton(
            self, text=label, variable=var,
            bg=C["panel"], fg=C["text"],
            activebackground=C["panel"], activeforeground=C["text"],
            selectcolor=C["primary"], font=FONT_LABEL, cursor="hand2"
        ).pack(side="left", anchor="w")


# ── Main App ───────────────────────────────────────────────────────────────────

class StatChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Stat Chat — Data Analysis Tool")
        self.root.geometry("1200x820")
        self.root.minsize(1000, 680)
        self.root.configure(bg=C["bg"])

        # State
        self.original_df: pd.DataFrame | None = None
        self.cleaned_df:  pd.DataFrame | None = None   # current working copy
        self.working_df:  pd.DataFrame | None = None   # post-adjustment working copy
        self.analysis_results: dict = {}
        self.source_file:  str = ""
        self.source_ext:   str = ".csv"
        self._clean_log:   list = []
        self._norm_log:    list = []
        # These are created during _build_ui; pre-declare to avoid AttributeError
        self._backend_label    = None
        self._left_backend_var = None

        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_titlebar()
        content = tk.Frame(self.root, bg=C["bg"])
        content.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        content.columnconfigure(0, weight=0, minsize=320)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        self._build_left_panel(content)
        self._build_right_panel(content)

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=C["card"], height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="Stat Chat", font=FONT_TITLE,
                 bg=C["card"], fg=C["text"]).pack(side="left", padx=18, pady=10)
        tk.Label(bar, text="Data Cleaning · Normalization · Statistical Analysis · Iterative Adjustment",
                 font=FONT_SMALL, bg=C["card"], fg=C["muted"]).pack(side="left", pady=14)
        # Backend indicator + settings gear (right side)
        tk.Button(bar, text="⚙  Settings", font=FONT_SMALL,
                  bg=C["border"], fg=C["text"], relief="flat", cursor="hand2",
                  padx=10, pady=4,
                  command=self._open_settings).pack(side="right", padx=12, pady=10)
        self._backend_label = tk.Label(bar, text="", font=FONT_SMALL,
                                       bg=C["card"], fg=C["muted"])
        self._backend_label.pack(side="right", padx=(0,4), pady=10)
        self._update_backend_label()

    def _build_left_panel(self, parent):
        frame = tk.Frame(parent, bg=C["panel"], width=320)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=6)
        frame.pack_propagate(False)

        canvas = tk.Canvas(frame, bg=C["panel"], bd=0, highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self.left_inner = tk.Frame(canvas, bg=C["panel"])
        self.left_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.left_inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        p   = self.left_inner
        pad = {"padx": 12, "pady": 4}

        # File
        SectionLabel(p, "📂  File").pack(fill="x", **pad)
        self.file_var = tk.StringVar(value="No file loaded")
        tk.Label(p, textvariable=self.file_var, font=FONT_SMALL,
                 bg=C["panel"], fg=C["muted"], wraplength=280, anchor="w").pack(fill="x", padx=12)
        StyledButton(p, "Load CSV / Excel", self._load_file).pack(fill="x", padx=12, pady=(4,8))
        ttk.Separator(p, orient="horizontal").pack(fill="x", padx=10, pady=4)

        # Cleaning
        SectionLabel(p, "🧹  Data Cleaning").pack(fill="x", **pad)
        self.v_drop_dup   = tk.BooleanVar()
        self.v_drop_nulls = tk.BooleanVar()
        self.v_fill_nulls = tk.BooleanVar()
        self.fill_strategy = tk.StringVar(value="mean")
        CheckRow(p, "Drop duplicate rows",    self.v_drop_dup).pack(fill="x", padx=12)
        CheckRow(p, "Drop rows with nulls",   self.v_drop_nulls).pack(fill="x", padx=12)
        ff = tk.Frame(p, bg=C["panel"]); ff.pack(fill="x", padx=12)
        tk.Checkbutton(ff, text="Fill missing values →", variable=self.v_fill_nulls,
                       bg=C["panel"], fg=C["text"], activebackground=C["panel"],
                       selectcolor=C["primary"], font=FONT_LABEL, cursor="hand2").pack(side="left")
        ttk.Combobox(ff, textvariable=self.fill_strategy, width=8,
                     values=["mean","median","mode","zero"], state="readonly").pack(side="left", padx=4)
        ttk.Separator(p, orient="horizontal").pack(fill="x", padx=10, pady=4)

        # Normalization
        SectionLabel(p, "📐  Normalization").pack(fill="x", **pad)
        self.norm_method = tk.StringVar(value="none")
        for val, lbl in [("none","None"),("zscore","Z-score"),("minmax","Min-Max"),("robust","Robust")]:
            tk.Radiobutton(p, text=lbl, variable=self.norm_method, value=val,
                           bg=C["panel"], fg=C["text"], activebackground=C["panel"],
                           selectcolor=C["primary"], font=FONT_LABEL).pack(anchor="w", padx=16)
        pf = tk.Frame(p, bg=C["panel"]); pf.pack(fill="x", padx=12, pady=(4,0))
        tk.Label(pf, text="Mean:", font=FONT_SMALL, bg=C["panel"], fg=C["muted"]).grid(row=0, column=0, sticky="w")
        self.norm_mean_var = tk.StringVar(value="0.0")
        tk.Entry(pf, textvariable=self.norm_mean_var, width=7,
                 bg=C["border"], fg=C["text"], insertbackground=C["text"], relief="flat").grid(row=0, column=1, padx=4)
        tk.Label(pf, text="Std:", font=FONT_SMALL, bg=C["panel"], fg=C["muted"]).grid(row=0, column=2, sticky="w")
        self.norm_std_var = tk.StringVar(value="1.0")
        tk.Entry(pf, textvariable=self.norm_std_var, width=7,
                 bg=C["border"], fg=C["text"], insertbackground=C["text"], relief="flat").grid(row=0, column=3, padx=4)
        tk.Label(pf, text="(z-score only)", font=FONT_SMALL, bg=C["panel"], fg=C["muted"]).grid(row=1, column=0, columnspan=4, sticky="w")
        ttk.Separator(p, orient="horizontal").pack(fill="x", padx=10, pady=4)

        # Analysis metrics
        SectionLabel(p, "📊  Analysis Metrics").pack(fill="x", **pad)
        self.v_central     = tk.BooleanVar(value=True)
        self.v_dispersion  = tk.BooleanVar(value=True)
        self.v_shape       = tk.BooleanVar()
        self.v_percentile  = tk.BooleanVar()
        self.v_normality   = tk.BooleanVar()
        self.v_correlation = tk.BooleanVar()
        self.v_roc_auc     = tk.BooleanVar()
        for var, lbl in [
            (self.v_central,    "Measures of Central Tendency"),
            (self.v_dispersion, "Measures of Dispersion"),
            (self.v_shape,      "Shape (Skewness & Kurtosis)"),
            (self.v_percentile, "Percentile Statistics"),
            (self.v_normality,  "Normality Tests (Shapiro-Wilk)"),
            (self.v_correlation,"Correlation Matrix"),
            (self.v_roc_auc,    "ROC-AUC"),
        ]:
            CheckRow(p, lbl, var).pack(fill="x", padx=12)
        rf = tk.Frame(p, bg=C["panel"]); rf.pack(fill="x", padx=16, pady=(2,0))
        tk.Label(rf, text="Target column:", font=FONT_SMALL, bg=C["panel"], fg=C["muted"]).pack(side="left")
        self.roc_target_var = tk.StringVar()
        tk.Entry(rf, textvariable=self.roc_target_var, width=14,
                 bg=C["border"], fg=C["text"], insertbackground=C["text"], relief="flat").pack(side="left", padx=6)
        ttk.Separator(p, orient="horizontal").pack(fill="x", padx=10, pady=4)

        # Actions
        SectionLabel(p, "⚙️  Actions").pack(fill="x", **pad)
        StyledButton(p, "▶  Run Analysis",       self._run_analysis,  color=C["success"]).pack(fill="x", padx=12, pady=3)
        StyledButton(p, "💾  Save Cleaned Data",  self._save_cleaned,  color=C["accent"]).pack(fill="x", padx=12, pady=3)
        StyledButton(p, "📄  Export PDF Report",  self._export_pdf,    color=C["warning"]).pack(fill="x", padx=12, pady=3)
        StyledButton(p, "🔄  Reset All",           self._reset,         color=C["danger"]).pack(fill="x", padx=12, pady=3)
        ttk.Separator(p, orient="horizontal").pack(fill="x", padx=10, pady=6)
        SectionLabel(p, "🤖  AI Backend").pack(fill="x", **pad)
        self._left_backend_var = tk.StringVar(value="")
        tk.Label(p, textvariable=self._left_backend_var, font=FONT_SMALL,
                 bg=C["panel"], fg=C["muted"], wraplength=280, anchor="w").pack(fill="x", padx=12)
        StyledButton(p, "⚙  Backend Settings",   self._open_settings, color=C["card"]).pack(fill="x", padx=12, pady=(4,10))

    def _build_right_panel(self, parent):
        frame = tk.Frame(parent, bg=C["bg"])
        frame.grid(row=0, column=1, sticky="nsew", pady=6)
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready · Load a file to begin.")
        tk.Label(frame, textvariable=self.status_var, font=FONT_SMALL,
                 bg=C["card"], fg=C["muted"], anchor="w", padx=10, pady=5).grid(row=0, column=0, sticky="ew")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=C["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=C["panel"], foreground=C["muted"],
                        padding=[14, 6], font=FONT_LABEL)
        style.map("TNotebook.Tab",
                  background=[("selected", C["primary"])],
                  foreground=[("selected", C["text"])])

        self.nb = ttk.Notebook(frame)
        self.nb.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        # Tab 0 — Data Preview
        self.tab_data = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(self.tab_data, text="  Data Preview  ")
        self._build_data_tab()

        # Tab 1 — Results
        self.tab_results = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(self.tab_results, text="  Analysis Results  ")
        self._build_results_tab()

        # Tab 2 — Adjust Data (chat panel)
        self.tab_adjust = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(self.tab_adjust, text="  ✦ Adjust Data  ")
        self._build_adjust_tab()

        # Tab 3 — Log
        self.tab_log = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(self.tab_log, text="  Log  ")
        self._build_log_tab()

    def _build_data_tab(self):
        f = self.tab_data
        f.rowconfigure(1, weight=1)
        f.columnconfigure(0, weight=1)
        self.data_info_var = tk.StringVar(value="No data loaded.")
        tk.Label(f, textvariable=self.data_info_var, font=FONT_SMALL,
                 bg=C["bg"], fg=C["muted"], anchor="w", padx=6, pady=4).grid(row=0, column=0, sticky="ew")
        tf = tk.Frame(f, bg=C["bg"])
        tf.grid(row=1, column=0, sticky="nsew")
        tf.rowconfigure(0, weight=1); tf.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tf, show="headings")
        vsb = ttk.Scrollbar(tf, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        s = ttk.Style()
        s.configure("Treeview", background=C["panel"], foreground=C["text"],
                    rowheight=24, fieldbackground=C["panel"], font=FONT_MONO)
        s.configure("Treeview.Heading", background=C["card"], foreground=C["highlight"],
                    font=("Segoe UI", 9, "bold"))
        s.map("Treeview", background=[("selected", C["primary"])])

    def _build_results_tab(self):
        f = self.tab_results
        f.rowconfigure(0, weight=1); f.columnconfigure(0, weight=1)
        self.results_text = scrolledtext.ScrolledText(
            f, bg=C["panel"], fg=C["text"], font=FONT_MONO,
            insertbackground=C["text"], relief="flat", padx=12, pady=10, state="disabled")
        self.results_text.pack(fill="both", expand=True)

    def _build_adjust_tab(self):
        f = self.tab_adjust
        f.rowconfigure(0, weight=1); f.columnconfigure(0, weight=1)
        self.adjust_panel = AdjustPanel(
            parent=f,
            get_df=lambda: self.working_df if self.working_df is not None else self.cleaned_df,
            on_apply=self._on_adjustment_applied,
            get_columns=lambda: list(self.working_df.columns) if self.working_df is not None
                                 else (list(self.cleaned_df.columns) if self.cleaned_df is not None else []),
            get_source_ext=lambda: self.source_ext,
            log_fn=self._log,
        )
        self.adjust_panel.grid(row=0, column=0, sticky="nsew")

    def _build_log_tab(self):
        f = self.tab_log
        f.rowconfigure(0, weight=1); f.columnconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(
            f, bg=C["bg"], fg=C["muted"], font=FONT_MONO,
            insertbackground=C["text"], relief="flat", padx=10, pady=8, state="disabled")
        self.log_text.pack(fill="both", expand=True)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.status_var.set(msg)

    def _show_results(self, text: str):
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.insert("end", text)
        self.results_text.configure(state="disabled")

    def _populate_table(self, df: pd.DataFrame, max_rows: int = 200):
        tree = self.tree
        tree.delete(*tree.get_children())
        cols = list(df.columns)
        tree["columns"] = cols
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=max(80, min(160, len(col)*10)), minwidth=60)
        for _, row in df.head(max_rows).iterrows():
            tree.insert("", "end", values=[str(v) if not pd.isna(v) else "" for v in row])
        n = len(df)
        self.data_info_var.set(
            f"Showing {min(n,max_rows)} of {n} rows · {len(cols)} columns"
            + (f"  (truncated to {max_rows})" if n > max_rows else ""))

    def _current_df(self) -> pd.DataFrame | None:
        """Returns the most up-to-date working DataFrame."""
        return self.working_df if self.working_df is not None else self.cleaned_df

    # ── Adjustment callback ────────────────────────────────────────────────────

    def _on_adjustment_applied(self, new_df: pd.DataFrame, description: str,
                                ops: list, request_report: bool = False):
        """Called by AdjustPanel when the user accepts a change or requests a report."""
        self.working_df = new_df
        self.root.after(0, lambda: self._populate_table(new_df))
        self._log(f"[adjust] {description}")

        if request_report:
            self.root.after(0, self._export_pdf_on_working)

    # ── Actions ────────────────────────────────────────────────────────────────

    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Open data file",
            filetypes=[("Data files", "*.csv *.xlsx *.xls *.xlsm"),
                       ("CSV", "*.csv"), ("Excel", "*.xlsx *.xls *.xlsm")])
        if not path:
            return
        try:
            self.original_df = load_file(path)
            self.cleaned_df  = self.original_df.copy()
            self.working_df  = None
            self.source_file = path
            self.source_ext  = Path(path).suffix or ".csv"
            info = get_file_info(self.original_df)
            self.file_var.set(Path(path).name)
            self._populate_table(self.original_df)
            self._log(f"Loaded: {Path(path).name}  ({info['rows']} rows, {info['columns']} cols)")
            self._log(f"  Numeric: {info['numeric_columns']}")
            self._log(f"  Missing: {sum(info['missing_values'].values())}  "
                      f"Dupes: {info['duplicate_rows']}")
            # Seed the adjust panel's version history
            self.adjust_panel.push_initial_version(self.original_df)
            self.adjust_panel.refresh_hints()
            self.nb.select(0)
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _run_analysis(self):
        if self.original_df is None:
            messagebox.showwarning("No Data", "Please load a file first.")
            return

        def worker():
            self._log("── Running preprocessing & analysis…")

            # Cleaning
            clean_opts = {
                "drop_duplicates": self.v_drop_dup.get(),
                "drop_nulls":      self.v_drop_nulls.get(),
                "fill_nulls":      self.fill_strategy.get() if self.v_fill_nulls.get() else None,
            }
            # Use working_df as base if adjustments have been made, else original
            base = (self.working_df if self.working_df is not None
                    else self.original_df).copy()
            df, clean_log = apply_cleaning(base, clean_opts)
            for msg in clean_log:
                self._log(f"  [clean] {msg}")
            self._clean_log = clean_log

            # Normalization
            try:
                nm = float(self.norm_mean_var.get())
                ns = float(self.norm_std_var.get())
            except ValueError:
                nm, ns = 0.0, 1.0
            norm_opts = {
                "normalize": None if self.norm_method.get() == "none" else self.norm_method.get(),
                "norm_mean": nm,
                "norm_std":  ns,
            }
            df, norm_log = apply_normalization(df, norm_opts)
            for msg in norm_log:
                self._log(f"  [norm] {msg}")
            self._norm_log = norm_log

            self.cleaned_df = df
            self.root.after(0, lambda: self._populate_table(df))

            # Restore binary target for ROC-AUC
            roc_target = self.roc_target_var.get().strip() if self.v_roc_auc.get() else None
            df_for_analysis = df.copy().reset_index(drop=True)
            ref_df = self.working_df if self.working_df is not None else self.original_df
            if roc_target and roc_target in ref_df.columns:
                df_for_analysis[roc_target] = ref_df[roc_target].reset_index(drop=True)

            analysis_opts = {
                "central_tendency": self.v_central.get(),
                "dispersion":       self.v_dispersion.get(),
                "shape":            self.v_shape.get(),
                "percentiles":      self.v_percentile.get(),
                "normality":        self.v_normality.get(),
                "correlation":      self.v_correlation.get(),
                "roc_auc":          roc_target,
                "all_metrics":      False,
                "original_df":      ref_df,
            }
            results = run_analysis(df_for_analysis, analysis_opts)
            self.analysis_results = results

            output = self._format_results(results)
            self.root.after(0, lambda: self._show_results(output))
            self.root.after(0, lambda: self.nb.select(1))
            self._log("── Analysis complete. Switch to ✦ Adjust Data to iterate.")

        threading.Thread(target=worker, daemon=True).start()

    def _format_results(self, results: dict) -> str:
        lines = ["Stat Chat — Analysis Results", "=" * 60, ""]
        for section, data in results.items():
            title = section.replace("_", " ").title()
            lines += [f"{'─'*60}", f"  {title}", f"{'─'*60}"]
            if section == "error":
                lines.append(f"  ERROR: {data}\n"); continue
            if section == "correlation":
                if isinstance(data, pd.DataFrame):
                    lines.append(data.round(4).to_string())
                lines.append(""); continue
            if section == "roc_auc":
                if "error" in data:
                    lines.append(f"  ERROR: {data['error']}")
                else:
                    for col, v in data.items():
                        if "auc" in v:
                            lines.append(f"  {col:30s}  AUC = {v['auc']:.4f}")
                        elif "error" in v:
                            lines.append(f"  {col:30s}  ERROR: {v['error']}")
                lines.append(""); continue
            for col, vals in data.items():
                if isinstance(vals, dict):
                    kv = "   ".join(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}"
                                    for k, v in vals.items())
                    lines.append(f"  {col:25s}  {kv}")
            lines.append("")
        return "\n".join(lines)

    def _save_cleaned(self):
        df = self._current_df()
        if df is None:
            messagebox.showwarning("No Data", "Please load a file first.")
            return
        ext = self.source_ext or ".csv"
        path = filedialog.asksaveasfilename(
            title="Save data",
            defaultextension=ext,
            filetypes=[("CSV","*.csv"),("Excel","*.xlsx"),("JSON","*.json")])
        if not path:
            return
        fmt = Path(path).suffix.lstrip(".") or "csv"
        try:
            out = save_file(df, path, fmt=fmt)
            self._log(f"Saved → {out}")
            messagebox.showinfo("Saved", f"Data saved to:\n{out}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _export_pdf(self):
        """Export PDF using the current working/cleaned df."""
        self._export_pdf_on_working()

    def _export_pdf_on_working(self):
        if self.original_df is None:
            messagebox.showwarning("No Data", "Please load a file first.")
            return
        ext_initial = Path(self.source_file).stem if self.source_file else "report"
        path = filedialog.asksaveasfilename(
            title="Save PDF Report",
            defaultextension=".pdf",
            filetypes=[("PDF","*.pdf")],
            initialfile=f"{ext_initial}_report")
        if not path:
            return

        # Collect adjustment history from the panel
        adj_history = self.adjust_panel._history if hasattr(self.adjust_panel, "_history") else []

        def worker():
            self._log("── Generating PDF report…")
            try:
                from core.reporter import generate_report
                _cur = self._current_df()
                display_df = _cur if _cur is not None else self.original_df
                out = generate_report(
                    filepath=path,
                    original_df=self.original_df,
                    cleaned_df=display_df,
                    analysis_results=self.analysis_results,
                    clean_log=self._clean_log,
                    norm_log=self._norm_log,
                    source_file=self.source_file,
                    adjustment_history=adj_history,
                )
                self._log(f"Report saved → {out}")
                self.root.after(0, lambda: messagebox.showinfo("PDF Saved", f"Report saved to:\n{out}"))
            except Exception as e:
                self._log(f"[ERROR] PDF generation failed: {e}")
                self.root.after(0, lambda: messagebox.showerror("PDF Error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _reset(self):
        self.original_df = None
        self.cleaned_df  = None
        self.working_df  = None
        self.analysis_results = {}
        self.source_file  = ""
        self.source_ext   = ".csv"
        self._clean_log   = []
        self._norm_log    = []
        self.file_var.set("No file loaded")
        self.data_info_var.set("No data loaded.")
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = []
        self._show_results("")
        self._log("── Reset. Load a new file to begin.")
        self.nb.select(0)
    # ── Backend settings ───────────────────────────────────────────────────────

    def _update_backend_label(self):
        """Refresh the backend indicator shown in titlebar and left panel."""
        cfg = get_config()
        labels = {
            "claude":          "☁  Claude API",
            "lmstudio":        "🖥  LM Studio (text)",
            "lmstudio_vision": "👁  LM Studio (vision)",
        }
        txt = labels.get(cfg.provider, cfg.provider)
        if cfg.provider in ("lmstudio", "lmstudio_vision"):
            model = cfg.lmstudio_vision_model if cfg.provider == "lmstudio_vision" else cfg.lmstudio_model
            if model:
                short = model.split("/")[-1][:24]
                txt += f"  ·  {short}"
            txt += f"  ·  {cfg.lmstudio_base_url}"
        if self._backend_label:
            self._backend_label.config(text=txt)
        if self._left_backend_var:
            self._left_backend_var.set(txt)

    def _open_settings(self):
        from gui.settings_dialog import SettingsDialog
        def on_save(cfg):
            self._update_backend_label()
            self._log(f"[settings] Backend set to: {cfg.provider}")
            if cfg.provider in ("lmstudio", "lmstudio_vision"):
                self._log(f"[settings] URL: {cfg.lmstudio_base_url}")
        SettingsDialog(self.root, current_cfg=get_config(), on_save=on_save)

