"""
gui/settings_dialog.py
----------------------
Modal settings window for configuring the LLM backend.
Lets the user switch between:
  • Claude API  (cloud, requires Anthropic API key injected by claude.ai)
  • LM Studio   (local text model via OpenAI-compatible API)
  • LM Studio Vision (local multimodal model for annotated-image input)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

C = {
    "bg":       "#0F172A",
    "panel":    "#1E293B",
    "card":     "#1E3A5F",
    "border":   "#334155",
    "primary":  "#2563EB",
    "success":  "#059669",
    "warning":  "#D97706",
    "danger":   "#DC2626",
    "text":     "#F1F5F9",
    "muted":    "#94A3B8",
    "highlight":"#0EA5E9",
}
FONT_LABEL = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 8)
FONT_H2    = ("Segoe UI", 11, "bold")
FONT_MONO  = ("Consolas", 9)
FONT_BTN   = ("Segoe UI", 10, "bold")


class SettingsDialog(tk.Toplevel):
    """
    Opens as a modal window.  On OK, calls on_save(LLMConfig).
    """

    def __init__(self, parent, current_cfg, on_save):
        super().__init__(parent)
        self.title("Stat Chat — Backend Settings")
        self.geometry("560x580")
        self.resizable(False, False)
        self.configure(bg=C["bg"])
        self.grab_set()          # modal
        self.focus_set()

        self._cfg      = current_cfg
        self._on_save  = on_save
        self._test_var = tk.StringVar(value="")

        self._build()
        self._load_current()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        # Title bar
        hdr = tk.Frame(self, bg=C["card"], height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="LLM Backend Settings", font=FONT_H2,
                 bg=C["card"], fg=C["text"]).pack(side="left", padx=16, pady=10)

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=14)

        # ── Provider selector ─────────────────────────────────────────────────
        tk.Label(body, text="Provider", font=FONT_H2,
                 bg=C["bg"], fg=C["highlight"], anchor="w").grid(
                     row=0, column=0, columnspan=2, sticky="w", pady=(0,4))

        self._provider = tk.StringVar(value="claude")
        providers = [
            ("claude",           "☁  Claude API  (cloud · no local setup needed)"),
            ("lmstudio",         "🖥  LM Studio — Text model  (local)"),
            ("lmstudio_vision",  "👁  LM Studio — Vision model  (local · for image annotations)"),
        ]
        for val, lbl in providers:
            tk.Radiobutton(
                body, text=lbl, variable=self._provider, value=val,
                bg=C["bg"], fg=C["text"], activebackground=C["bg"],
                selectcolor=C["primary"], font=FONT_LABEL,
                command=self._on_provider_change,
            ).grid(row=providers.index((val,lbl))+1, column=0, columnspan=2,
                   sticky="w", padx=8, pady=2)

        ttk.Separator(body, orient="horizontal").grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=10)

        # ── LM Studio settings ────────────────────────────────────────────────
        self._lm_frame = tk.Frame(body, bg=C["bg"])
        self._lm_frame.grid(row=5, column=0, columnspan=2, sticky="ew")

        def lbl(row, text):
            tk.Label(self._lm_frame, text=text, font=FONT_LABEL,
                     bg=C["bg"], fg=C["muted"], anchor="w").grid(
                         row=row, column=0, sticky="w", pady=3)

        def entry(row, var, width=36):
            e = tk.Entry(self._lm_frame, textvariable=var, width=width,
                         bg=C["panel"], fg=C["text"], insertbackground=C["text"],
                         relief="flat", font=FONT_MONO)
            e.grid(row=row, column=1, sticky="ew", padx=(10,0), pady=3)
            return e

        self._lm_frame.columnconfigure(1, weight=1)

        self._base_url_var = tk.StringVar(value="http://localhost:1234")
        lbl(0, "Server URL")
        entry(0, self._base_url_var)

        self._model_var = tk.StringVar()
        lbl(1, "Text model ID")
        self._model_entry = entry(1, self._model_var)

        self._vision_model_var = tk.StringVar()
        lbl(2, "Vision model ID")
        self._vision_entry = entry(2, self._vision_model_var)

        self._timeout_var = tk.StringVar(value="60")
        lbl(3, "Timeout (sec)")
        entry(3, self._timeout_var, width=8)

        self._temp_var = tk.StringVar(value="0.0")
        lbl(4, "Temperature")
        entry(4, self._temp_var, width=8)

        # Model list refresh
        refresh_row = tk.Frame(self._lm_frame, bg=C["bg"])
        refresh_row.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6,0))
        tk.Button(
            refresh_row, text="↻  Fetch loaded models",
            bg=C["border"], fg=C["text"], relief="flat", font=FONT_SMALL,
            cursor="hand2", padx=8, pady=3,
            command=self._fetch_models,
        ).pack(side="left")
        self._model_list_var = tk.StringVar(value="")
        tk.Label(refresh_row, textvariable=self._model_list_var,
                 font=FONT_SMALL, bg=C["bg"], fg=C["muted"],
                 wraplength=340, justify="left").pack(side="left", padx=8)

        # Help note
        note = (
            "Start LM Studio → Developer tab → ✓ Enable local server → Start Server.\n"
            "Load a text model for chat; load a multimodal model (e.g. LLaVA, BakLLaVA,\n"
            "Moondream) for vision annotation parsing.  Leave model ID blank to use\n"
            "whichever model is currently loaded."
        )
        tk.Label(body, text=note, font=FONT_SMALL,
                 bg=C["card"], fg=C["muted"], justify="left",
                 padx=10, pady=8, wraplength=500).grid(
                     row=6, column=0, columnspan=2, sticky="ew", pady=(10,0))

        # ── Test connection ───────────────────────────────────────────────────
        ttk.Separator(body, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=10)

        test_row = tk.Frame(body, bg=C["bg"])
        test_row.grid(row=8, column=0, columnspan=2, sticky="ew")
        tk.Button(
            test_row, text="🔌  Test Connection",
            bg=C["primary"], fg=C["text"], relief="flat", font=FONT_BTN,
            cursor="hand2", padx=12, pady=5,
            command=self._test_connection,
        ).pack(side="left")
        self._test_indicator = tk.Label(
            test_row, text="", font=FONT_SMALL,
            bg=C["bg"], fg=C["muted"], wraplength=340, justify="left")
        self._test_indicator.pack(side="left", padx=10)

        # ── Footer buttons ────────────────────────────────────────────────────
        footer = tk.Frame(self, bg=C["panel"])
        footer.pack(fill="x", side="bottom")
        tk.Button(
            footer, text="Cancel",
            bg=C["border"], fg=C["text"], relief="flat", font=FONT_BTN,
            cursor="hand2", padx=14, pady=7,
            command=self.destroy,
        ).pack(side="right", padx=10, pady=8)
        tk.Button(
            footer, text="Save & Close",
            bg=C["success"], fg=C["text"], relief="flat", font=FONT_BTN,
            cursor="hand2", padx=14, pady=7,
            command=self._save,
        ).pack(side="right", pady=8)

        self._on_provider_change()

    # ── State helpers ─────────────────────────────────────────────────────────

    def _load_current(self):
        cfg = self._cfg
        self._provider.set(cfg.provider)
        self._base_url_var.set(cfg.lmstudio_base_url)
        self._model_var.set(cfg.lmstudio_model)
        self._vision_model_var.set(cfg.lmstudio_vision_model)
        self._timeout_var.set(str(cfg.timeout))
        self._temp_var.set(str(cfg.temperature))
        self._on_provider_change()

    def _on_provider_change(self):
        p = self._provider.get()
        is_lm = p in ("lmstudio", "lmstudio_vision")
        state = "normal" if is_lm else "disabled"
        for w in self._lm_frame.winfo_children():
            try:
                w.configure(state=state)
            except tk.TclError:
                pass

    def _fetch_models(self):
        from core.llm_backend import list_lmstudio_models
        url = self._base_url_var.get().strip()
        self._model_list_var.set("Fetching…")

        def worker():
            models = list_lmstudio_models(url)
            if models:
                txt = "Loaded: " + " · ".join(models)
                # Auto-fill model field if blank
                if not self._model_var.get():
                    self.after(0, lambda: self._model_var.set(models[0]))
            else:
                txt = "No models found (is LM Studio running?)"
            self.after(0, lambda: self._model_list_var.set(txt))

        threading.Thread(target=worker, daemon=True).start()

    def _test_connection(self):
        self._test_indicator.config(text="Testing…", fg=C["muted"])
        cfg = self._build_config()

        def worker():
            from core.llm_backend import test_connection
            ok, msg = test_connection(cfg)
            color = C["success"] if ok else C["danger"]
            prefix = "✓  " if ok else "✗  "
            self.after(0, lambda: self._test_indicator.config(
                text=prefix + msg[:120], fg=color))

        threading.Thread(target=worker, daemon=True).start()

    def _build_config(self):
        from core.llm_backend import LLMConfig
        try:
            timeout = int(self._timeout_var.get())
        except ValueError:
            timeout = 60
        try:
            temp = float(self._temp_var.get())
        except ValueError:
            temp = 0.0
        return LLMConfig(
            provider=self._provider.get(),
            lmstudio_base_url=self._base_url_var.get().strip(),
            lmstudio_model=self._model_var.get().strip(),
            lmstudio_vision_model=self._vision_model_var.get().strip(),
            timeout=timeout,
            temperature=temp,
        )

    def _save(self):
        cfg = self._build_config()
        from core.llm_backend import set_config
        set_config(cfg)
        self._on_save(cfg)
        self.destroy()
