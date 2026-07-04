#!/usr/bin/env python3
"""
Stat Chat — Data Cleaning, Normalization, Statistical Analysis & Iterative Adjustment

Entry points:
  GUI:  statchat
  CLI:  statchat --cli --input data.csv [options]
  Also: python -m statchat
"""

import argparse
import sys


# ── Dependency check ───────────────────────────────────────────────────────────

REQUIRED = {
    "pandas":      "pandas",
    "numpy":       "numpy",
    "scipy":       "scipy",
    "sklearn":     "scikit-learn",
    "reportlab":   "reportlab",
    "matplotlib":  "matplotlib",
    "openpyxl":    "openpyxl",
    "requests":    "requests",
    "PIL":         "Pillow",
}


def check_dependencies():
    missing = []
    for module, pip_name in REQUIRED.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pip_name)
    return missing


def prompt_install(missing):
    cmd = "pip install " + " ".join(missing)
    print("=" * 60)
    print("  Stat Chat — Missing Dependencies")
    print("=" * 60)
    print(f"\n  The following packages are required but not installed:\n")
    for p in missing:
        print(f"    • {p}")
    print(f"\n  Install them by running:\n\n    {cmd}\n")

    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        answer = messagebox.askyesno(
            "Stat Chat — Missing packages",
            "The following required packages are missing:\n\n"
            + "\n".join(f"  • {p}" for p in missing)
            + f"\n\nInstall them now?\n\n{cmd}",
        )
        root.destroy()
        if answer:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            print("\n  ✓  Installation complete. Relaunch Stat Chat.")
    except Exception:
        pass

    sys.exit(1)


# ── Launchers ──────────────────────────────────────────────────────────────────

def run_gui():
    try:
        import tkinter as tk
    except ImportError:
        print("[ERROR] Tkinter is not available.")
        print("  Linux:        sudo apt install python3-tk")
        print("  macOS/Windows: reinstall Python from python.org")
        sys.exit(1)

    from statchat.gui.app import StatChatApp
    root = tk.Tk()
    StatChatApp(root)
    root.mainloop()


def run_cli(args):
    from statchat.cli.runner import CLIRunner
    CLIRunner(args).run()


# ── CLI argument parser ────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="statchat",
        description="Stat Chat — Data Cleaning, Normalization & Statistical Analysis",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (no GUI)")
    parser.add_argument("--input",  "-i", type=str, help="Input CSV or Excel file")
    parser.add_argument("--output", "-o", type=str, help="Path to save processed data")
    parser.add_argument("--output-format", choices=["csv", "xlsx", "json"], default="csv",
                        help="Output format (default: csv)")
    parser.add_argument("--report", "-r", type=str, help="Path to save PDF report")

    cg = parser.add_argument_group("Cleaning Options")
    cg.add_argument("--drop-duplicates", action="store_true", help="Remove duplicate rows")
    cg.add_argument("--drop-nulls",      action="store_true", help="Drop rows with null values")
    cg.add_argument("--fill-nulls", choices=["mean", "median", "mode", "zero"],
                    help="Fill null values with strategy")

    ng = parser.add_argument_group("Normalization Options")
    ng.add_argument("--normalize", choices=["zscore", "minmax", "robust"],
                    help="Normalization method")
    ng.add_argument("--norm-mean", type=float, default=0.0,
                    help="Z-score target mean (default: 0.0)")
    ng.add_argument("--norm-std",  type=float, default=1.0,
                    help="Z-score target std  (default: 1.0)")

    ag = parser.add_argument_group("Analysis Metrics")
    ag.add_argument("--central-tendency", action="store_true", help="Mean, median, mode")
    ag.add_argument("--dispersion",       action="store_true", help="Std dev, variance, IQR, range")
    ag.add_argument("--shape",            action="store_true", help="Skewness & kurtosis")
    ag.add_argument("--correlation",      action="store_true", help="Correlation matrix")
    ag.add_argument("--percentiles",      action="store_true", help="P5–P95 percentiles")
    ag.add_argument("--roc-auc", type=str, metavar="TARGET_COL",
                    help="ROC-AUC vs a binary target column")
    ag.add_argument("--all-metrics", action="store_true", help="Run all metrics")

    adj = parser.add_argument_group("Adjustment Options (requires LLM backend)")
    adj.add_argument("--adjust", action="append", metavar="INSTRUCTION",
                     help="Natural-language adjustment (repeatable).\n"
                          "e.g. --adjust 'Add 1000 to spend'")
    adj.add_argument("--adjust-image", type=str, metavar="IMAGE_PATH",
                     help="Annotated report image — vision model extracts instructions")

    bg = parser.add_argument_group("LLM Backend Options")
    bg.add_argument("--backend", choices=["claude", "lmstudio", "lmstudio_vision"],
                    default="claude", help="LLM provider (default: claude)")
    bg.add_argument("--lmstudio-url",          type=str, default="http://localhost:1234",
                    metavar="URL",      help="LM Studio server URL")
    bg.add_argument("--lmstudio-model",        type=str, default="", metavar="MODEL_ID",
                    help="LM Studio text model ID")
    bg.add_argument("--lmstudio-vision-model", type=str, default="", metavar="MODEL_ID",
                    help="LM Studio vision model ID")

    return parser


# ── Main entry point ───────────────────────────────────────────────────────────

def main():
    missing = check_dependencies()
    if missing:
        prompt_install(missing)

    parser = build_parser()
    args   = parser.parse_args()

    if args.cli:
        if not args.input:
            parser.error("--input is required in CLI mode")
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
