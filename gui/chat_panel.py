"""
gui/chat_panel.py
-----------------
A Tkinter widget that provides a chat-like interface for adjusting the dataset.
Embeds into the main Notebook as the "Adjust Data" tab.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import base64
import datetime
from pathlib import Path
import pandas as pd

# ── Colour tokens (same palette as app.py) ────────────────────────────────────
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
    "user_msg":  "#1E3A5F",
    "ai_msg":    "#1A2744",
    "diff_add":  "#052E16",
    "diff_hdr":  "#14532D",
}

FONT_LABEL = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 9)
FONT_BTN   = ("Segoe UI", 10, "bold")
FONT_H2    = ("Segoe UI", 11, "bold")


class StyledButton(tk.Button):
    def __init__(self, parent, text, command=None, color=None, **kwargs):
        color = color or C["primary"]
        super().__init__(
            parent, text=text, command=command,
            bg=color, fg=C["text"], activebackground=C["primary_h"],
            activeforeground=C["text"],
            relief="flat", bd=0, padx=12, pady=5,
            font=FONT_BTN, cursor="hand2", **kwargs
        )
        self._color = color
        self.bind("<Enter>", lambda e: self.config(bg=self._dk()))
        self.bind("<Leave>", lambda e: self.config(bg=self._color))

    def _dk(self):
        r, g, b = int(self._color[1:3],16), int(self._color[3:5],16), int(self._color[5:7],16)
        return "#{:02x}{:02x}{:02x}".format(max(0,r-30),max(0,g-30),max(0,b-30))


class AdjustPanel(tk.Frame):
    """
    Chat panel + version history sidebar.
    Calls back to the host app via:
      get_df()        → current working DataFrame
      on_apply(df, description, ops) → called after a successful adjustment
      get_columns()   → list of column names for the hint strip
      get_source_ext()→ original file extension
    """

    def __init__(self, parent, get_df, on_apply, get_columns, get_source_ext, log_fn):
        super().__init__(parent, bg=C["bg"])
        self._get_df      = get_df
        self._on_apply    = on_apply
        self._get_columns = get_columns
        self._get_ext     = get_source_ext
        self._log         = log_fn
        self._history: list[dict] = []   # [{version, df, description, timestamp}]
        self._pending_df  = None          # preview result waiting for confirmation

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0, minsize=220)
        self.rowconfigure(0, weight=1)

        self._build_chat_area()
        self._build_sidebar()

    # ── Chat area ─────────────────────────────────────────────────────────────

    def _build_chat_area(self):
        left = tk.Frame(self, bg=C["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.rowconfigure(0, weight=1)
        left.rowconfigure(1, weight=0)
        left.columnconfigure(0, weight=1)

        # Message canvas
        msg_outer = tk.Frame(left, bg=C["panel"], relief="flat")
        msg_outer.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        msg_outer.rowconfigure(0, weight=1)
        msg_outer.columnconfigure(0, weight=1)

        self._msg_canvas = tk.Canvas(msg_outer, bg=C["panel"], bd=0,
                                     highlightthickness=0)
        vsb = ttk.Scrollbar(msg_outer, orient="vertical",
                             command=self._msg_canvas.yview)
        self._msg_frame = tk.Frame(self._msg_canvas, bg=C["panel"])
        self._msg_frame.bind("<Configure>",
            lambda e: self._msg_canvas.configure(
                scrollregion=self._msg_canvas.bbox("all")))
        self._msg_canvas.create_window((0, 0), window=self._msg_frame, anchor="nw")
        self._msg_canvas.configure(yscrollcommand=vsb.set)
        self._msg_canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self._msg_canvas.bind_all("<MouseWheel>",
            lambda e: self._msg_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self._add_system_message(
            "💡 Describe adjustments in plain English, or upload an annotated report image\n"
            "   (requires a vision model in LM Studio or Claude API).\n\n"
            "Text examples:\n"
            "  • Add $1000 to each value in 'spend'\n"
            "  • Multiply income by 1.1\n"
            "  • Clip spend between 0 and 5000\n"
            "  • Remove rows where age < 18\n"
            "  • Log-transform spend\n\n"
            "Image: annotate a printed PDF with handwritten or typed notes,\n"
            "   take a photo or screenshot, then click 📷 Upload Annotated Image.\n\n"
            "Each accepted change is saved as a new version in the history sidebar."
        )

        # Column hint strip
        self._hint_var = tk.StringVar(value="Load a file to see available columns.")
        tk.Label(left, textvariable=self._hint_var, font=FONT_SMALL,
                 bg=C["border"], fg=C["muted"], anchor="w",
                 padx=8, pady=3, wraplength=500).grid(row=1, column=0, sticky="ew")

        # Input row
        input_frame = tk.Frame(left, bg=C["bg"])
        input_frame.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        input_frame.columnconfigure(0, weight=1)

        self._input_box = tk.Text(
            input_frame, height=3, bg=C["panel"], fg=C["text"],
            insertbackground=C["text"], relief="flat", font=FONT_LABEL,
            padx=10, pady=8, wrap="word"
        )
        self._input_box.grid(row=0, column=0, sticky="ew")
        self._input_box.bind("<Return>", self._on_return)
        self._input_box.bind("<Shift-Return>", lambda e: None)

        btn_col = tk.Frame(input_frame, bg=C["bg"])
        btn_col.grid(row=0, column=1, padx=(6, 0), sticky="ns")
        StyledButton(btn_col, "Send", self._send, color=C["primary"]).pack(fill="x", pady=(0,3))
        StyledButton(btn_col, "📷 Image", self._send_image, color=C["accent"]).pack(fill="x", pady=(0,3))
        StyledButton(btn_col, "Clear", self._clear_input, color=C["border"]).pack(fill="x")

        tk.Label(input_frame, text="Enter = send  |  Shift+Enter = newline  |  📷 = annotated image",
                 font=FONT_SMALL, bg=C["bg"], fg=C["muted"]).grid(
                     row=1, column=0, sticky="w", pady=(2, 0))

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        right = tk.Frame(self, bg=C["panel"], width=220)
        right.grid(row=0, column=1, sticky="nsew")
        right.pack_propagate(False)

        tk.Label(right, text="Version History", font=FONT_H2,
                 bg=C["panel"], fg=C["highlight"], anchor="w",
                 padx=10, pady=8).pack(fill="x")

        ttk.Separator(right, orient="horizontal").pack(fill="x", padx=8)

        list_frame = tk.Frame(right, bg=C["panel"])
        list_frame.pack(fill="both", expand=True, padx=6, pady=6)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self._version_list = tk.Listbox(
            list_frame, bg=C["bg"], fg=C["text"],
            selectbackground=C["primary"], selectforeground=C["text"],
            font=FONT_SMALL, relief="flat", bd=0,
            activestyle="none", cursor="hand2"
        )
        vsb2 = ttk.Scrollbar(list_frame, orient="vertical",
                              command=self._version_list.yview)
        self._version_list.configure(yscrollcommand=vsb2.set)
        self._version_list.grid(row=0, column=0, sticky="nsew")
        vsb2.grid(row=0, column=1, sticky="ns")
        self._version_list.bind("<<ListboxSelect>>", self._on_version_select)

        ttk.Separator(right, orient="horizontal").pack(fill="x", padx=8, pady=4)

        btn_pad = {"fill": "x", "padx": 8, "pady": 3}
        StyledButton(right, "↩  Revert to Selected",
                     self._revert_to_selected, color=C["warning"]).pack(**btn_pad)
        StyledButton(right, "💾  Save Selected Version",
                     self._save_selected_version, color=C["accent"]).pack(**btn_pad)
        StyledButton(right, "📄  Report on Selected",
                     self._report_on_selected, color=C["success"]).pack(**btn_pad)

        self._version_detail = tk.Label(
            right, text="", font=FONT_SMALL, bg=C["panel"], fg=C["muted"],
            wraplength=200, justify="left", anchor="nw", padx=8
        )
        self._version_detail.pack(fill="x", pady=(4, 0))

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh_hints(self):
        """Called by host app when a new file is loaded."""
        cols = self._get_columns()
        if cols:
            self._hint_var.set("Columns: " + "  ·  ".join(cols))
        else:
            self._hint_var.set("No data loaded.")
        # Seed version 0 = original
        df = self._get_df()
        if df is not None and not self._history:
            self._push_version(df.copy(), "Original dataset loaded", [])

    def push_initial_version(self, df: pd.DataFrame):
        """Called when a file is first loaded."""
        self._history.clear()
        self._version_list.delete(0, "end")
        self._push_version(df.copy(), "Original dataset", [])

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _push_version(self, df: pd.DataFrame, description: str, ops: list):
        v_num = len(self._history)
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._history.append({
            "version": v_num,
            "df": df.copy(),
            "description": description,
            "ops": ops,
            "timestamp": ts,
        })
        label = f"v{v_num}  {ts}\n{description[:32]}{'…' if len(description)>32 else ''}"
        self._version_list.insert("end", label)
        self._version_list.see("end")
        self._version_list.selection_clear(0, "end")
        self._version_list.selection_set("end")
        self._update_version_detail(self._history[-1])

    def _on_version_select(self, event=None):
        sel = self._version_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._history):
            self._update_version_detail(self._history[idx])

    def _update_version_detail(self, entry: dict):
        df = entry["df"]
        lines = [
            f"v{entry['version']}  ·  {entry['timestamp']}",
            f"Rows: {len(df)}  Cols: {len(df.columns)}",
            "",
            entry["description"],
        ]
        if entry["ops"]:
            lines += ["", "Operations:"] + [f"  • {op.get('description','')}" for op in entry["ops"]]
        self._version_detail.config(text="\n".join(lines))

    def _add_message(self, role: str, text: str, tag_color: str = None):
        """Append a message bubble to the chat frame."""
        outer = tk.Frame(self._msg_frame, bg=C["panel"], pady=4)
        outer.pack(fill="x", padx=8)

        label_text = "You" if role == "user" else "Stat Chat AI"
        label_color = C["highlight"] if role == "user" else C["success"]
        bg_color = C["user_msg"] if role == "user" else C["ai_msg"]
        if tag_color:
            bg_color = tag_color

        tk.Label(outer, text=label_text, font=("Segoe UI", 8, "bold"),
                 bg=C["panel"], fg=label_color, anchor="w").pack(fill="x")

        bubble = tk.Frame(outer, bg=bg_color, padx=12, pady=8)
        bubble.pack(fill="x")

        tk.Label(bubble, text=text, font=FONT_LABEL, bg=bg_color, fg=C["text"],
                 wraplength=520, justify="left", anchor="nw").pack(fill="x")

        self._msg_canvas.update_idletasks()
        self._msg_canvas.yview_moveto(1.0)

    def _add_system_message(self, text: str):
        outer = tk.Frame(self._msg_frame, bg=C["panel"], pady=6)
        outer.pack(fill="x", padx=8)
        tk.Label(outer, text=text, font=FONT_SMALL, bg=C["card"], fg=C["muted"],
                 wraplength=520, justify="left", anchor="nw",
                 padx=12, pady=8).pack(fill="x")
        self._msg_canvas.update_idletasks()
        self._msg_canvas.yview_moveto(1.0)

    def _add_diff_summary(self, original_df: pd.DataFrame, new_df: pd.DataFrame,
                           descriptions: list[str], ops: list[dict]):
        """Show a compact diff card with accept/reject buttons."""
        outer = tk.Frame(self._msg_frame, bg=C["panel"], pady=4)
        outer.pack(fill="x", padx=8)

        card = tk.Frame(outer, bg=C["diff_hdr"], padx=12, pady=10)
        card.pack(fill="x")

        tk.Label(card, text="✦ Proposed Changes", font=("Segoe UI", 10, "bold"),
                 bg=C["diff_hdr"], fg="#4ADE80", anchor="w").pack(fill="x")

        for d in descriptions:
            tk.Label(card, text=f"  • {d}", font=FONT_SMALL,
                     bg=C["diff_hdr"], fg=C["text"], anchor="w").pack(fill="x")

        # Row/col delta
        dr = len(new_df) - len(original_df)
        dc = len(new_df.columns) - len(original_df.columns)
        delta_parts = []
        if dr != 0:
            delta_parts.append(f"{'+'if dr>0 else ''}{dr} rows")
        if dc != 0:
            delta_parts.append(f"{'+'if dc>0 else ''}{dc} columns")

        # Numeric delta for changed columns
        num_cols_before = set(original_df.select_dtypes(include="number").columns)
        num_cols_after  = set(new_df.select_dtypes(include="number").columns)
        changed = num_cols_before & num_cols_after
        stat_lines = []
        for col in sorted(changed):
            try:
                before_mean = original_df[col].mean()
                after_mean  = new_df[col].mean()
                if abs(before_mean - after_mean) > 1e-9:
                    pct = ((after_mean - before_mean) / abs(before_mean) * 100) if before_mean != 0 else float('inf')
                    stat_lines.append(
                        f"  {col}: mean {before_mean:.3g} → {after_mean:.3g}  "
                        f"({'+'if pct>0 else ''}{pct:.1f}%)"
                    )
            except Exception:
                pass

        if delta_parts:
            tk.Label(card, text="  Shape: " + "  ".join(delta_parts), font=FONT_SMALL,
                     bg=C["diff_hdr"], fg=C["muted"], anchor="w").pack(fill="x", pady=(4,0))
        for sl in stat_lines[:6]:
            tk.Label(card, text=sl, font=FONT_MONO,
                     bg=C["diff_add"], fg="#86EFAC", anchor="w",
                     padx=4).pack(fill="x", pady=1)

        # Accept / Reject buttons
        btn_row = tk.Frame(card, bg=C["diff_hdr"])
        btn_row.pack(fill="x", pady=(8, 0))

        def _accept():
            self._pending_df = None
            self._on_apply(new_df.copy(), "; ".join(descriptions), ops)
            self._push_version(new_df.copy(), "; ".join(descriptions), ops)
            self._add_message("assistant",
                "✅ Changes applied. A new version has been saved to the history.")
            accept_btn.config(state="disabled")
            reject_btn.config(state="disabled")

        def _reject():
            self._pending_df = None
            self._add_message("assistant",
                "❌ Changes discarded. The dataset is unchanged.")
            accept_btn.config(state="disabled")
            reject_btn.config(state="disabled")

        accept_btn = StyledButton(btn_row, "✓  Accept Changes", _accept, color=C["success"])
        accept_btn.pack(side="left", padx=(0, 6))
        reject_btn = StyledButton(btn_row, "✕  Discard", _reject, color=C["danger"])
        reject_btn.pack(side="left")

        self._msg_canvas.update_idletasks()
        self._msg_canvas.yview_moveto(1.0)

    # ── Input handling ────────────────────────────────────────────────────────

    def _on_return(self, event):
        if not event.state & 0x1:   # Shift not held
            self._send()
            return "break"

    def _clear_input(self):
        self._input_box.delete("1.0", "end")

    def _send(self):
        text = self._input_box.get("1.0", "end").strip()
        if not text:
            return

        df = self._get_df()
        if df is None:
            messagebox.showwarning("No Data", "Please load a file first.")
            return

        self._input_box.delete("1.0", "end")
        self._add_message("user", text)
        self._add_message("assistant", "⏳ Interpreting instruction…")

        def worker():
            try:
                from core.adjuster import apply_instructions
                new_df, descriptions, ops = apply_instructions(df, text)

                # Remove the "thinking" message by rebuilding — simplest approach
                # is to just add the diff card
                self.after(0, lambda: self._replace_last_thinking(
                    original_df=df,
                    new_df=new_df,
                    descriptions=descriptions,
                    ops=ops
                ))

            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._replace_last_thinking_with_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _send_image(self):
        """Let the user pick an annotated image/screenshot and send it to the vision model."""
        from core.llm_backend import get_config
        cfg = get_config()

        df = self._get_df()
        if df is None:
            messagebox.showwarning("No Data", "Please load a file first.")
            return

        if cfg.provider not in ("claude", "lmstudio_vision"):
            messagebox.showinfo(
                "Vision Model Required",
                "Image annotation parsing requires either:\n"
                "  • Claude API (cloud)\n"
                "  • LM Studio with a vision model\n\n"
                "Go to ⚙ Backend Settings and select a vision-capable backend."
            )
            return

        path = filedialog.askopenfilename(
            title="Select annotated report image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff"),
                ("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg"),
            ]
        )
        if not path:
            return

        try:
            with open(path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not read image:\n{e}")
            return

        from pathlib import Path as _Path
        fname = _Path(path).name
        self._add_message("user", f"📷 Uploaded annotated image: {fname}")
        self._add_message("assistant", "⏳ Parsing instructions from image…")

        def worker():
            try:
                from core.adjuster import apply_instructions_from_image
                new_df, descriptions, ops = apply_instructions_from_image(df, image_b64)
                self.after(0, lambda: self._replace_last_thinking(
                    original_df=df,
                    new_df=new_df,
                    descriptions=descriptions,
                    ops=ops,
                ))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._replace_last_thinking_with_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _replace_last_thinking(self, original_df, new_df, descriptions, ops):
        """Remove the ⏳ bubble and add the diff card."""
        widgets = self._msg_frame.winfo_children()
        if widgets:
            widgets[-1].destroy()
        self._add_diff_summary(original_df, new_df, descriptions, ops)

    def _replace_last_thinking_with_error(self, error: str):
        widgets = self._msg_frame.winfo_children()
        if widgets:
            widgets[-1].destroy()
        self._add_message("assistant",
            f"⚠️ Could not apply instruction:\n{error}\n\n"
            "Try rephrasing — be specific about column names and operations.",
            tag_color=C["danger"])

    # ── Version actions ───────────────────────────────────────────────────────

    def _selected_version(self):
        sel = self._version_list.curselection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a version from the list first.")
            return None
        idx = sel[0]
        if idx < len(self._history):
            return self._history[idx]
        return None

    def _revert_to_selected(self):
        entry = self._selected_version()
        if entry is None:
            return
        if not messagebox.askyesno("Revert",
                f"Revert working dataset to v{entry['version']}: \"{entry['description']}\"?\n\n"
                "This will replace the current working data. "
                "A new version entry will be added."):
            return
        desc = f"Reverted to v{entry['version']}"
        self._on_apply(entry["df"].copy(), desc, [])
        self._push_version(entry["df"].copy(), desc, [])
        self._add_message("assistant",
            f"↩ Dataset reverted to v{entry['version']}. "
            "A new version entry has been added so you can track this revert.")
        self._log(f"[adjust] Reverted to v{entry['version']}")

    def _save_selected_version(self):
        entry = self._selected_version()
        if entry is None:
            return
        df = entry["df"]
        ext = self._get_ext() or ".csv"
        filetypes = [("CSV", "*.csv"), ("Excel", "*.xlsx"), ("JSON", "*.json")]
        default_ext = ext if ext.startswith(".") else "." + ext
        path = filedialog.asksaveasfilename(
            title=f"Save v{entry['version']}",
            defaultextension=default_ext,
            filetypes=filetypes,
            initialfile=f"dataset_v{entry['version']}"
        )
        if not path:
            return
        from core.loader import save_file
        fmt = Path(path).suffix.lstrip(".") or "csv"
        try:
            out = save_file(df, path, fmt=fmt)
            self._log(f"[adjust] Saved v{entry['version']} → {out}")
            messagebox.showinfo("Saved", f"v{entry['version']} saved to:\n{out}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _report_on_selected(self):
        entry = self._selected_version()
        if entry is None:
            return
        # Delegate back to host app via callback
        self._on_apply(entry["df"].copy(), f"Report on v{entry['version']}", [],
                       request_report=True)
