#!/usr/bin/env python3
"""
Stat Chat - A Python Data Analysis & Cleaning Tool
Supports both GUI (Tkinter) and CLI modes.
"""

import argparse
import sys
from pathlib import Path

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

    # If tkinter is available, show a GUI dialog too
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        answer = messagebox.askyesno(
            "Stat Chat — Missing packages",
            f"The following required packages are missing:\n\n"
            + "\n".join(f"  • {p}" for p in missing)
            + f"\n\nInstall them now?\n\n{cmd}",
        )
        root.destroy()
        if answer:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            print("\n  ✓  Installation complete. Relaunch Stat Chat.")
        else:
            print("\n  Install them manually, then relaunch.")
    except Exception:
        pass   # headless — text output is enough

    sys.exit(1)


# ── Launchers ──────────────────────────────────────────────────────────────────

def run_gui():
    """Launch the Tkinter GUI application."""
    try:
        import tkinter as tk
    except ImportError:
        print("[ERROR] Tkinter is not available.")
        print("  On Linux: sudo apt install python3-tk")
        print("  On macOS/Windows: reinstall Python from python.org (Tkinter is bundled).")
        sys.exit(1)

    from gui.app import StatChatApp
    root = tk.Tk()
    app = StatChatApp(root)
    root.mainloop()


def run_cli(args):
    """Run the application in CLI mode."""
    from cli.runner import CLIRunner
    runner = CLIRunner(args)
    runner.run()


# ── Argument parser ────────────────────────────────────────────────────────────

def main():
    # Always check deps first (fast — just import probes, no network)
    missing = check_dependencies()
    if missing:
        prompt_install(missing)

    sys.path.insert(0, str(Path(__file__).parent))

    parser = argparse.ArgumentParser(
        prog="statchat",
        description="Stat Chat — Data Cleaning, Normalization & Statistical Analysis Tool",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (no GUI)")
    parser.add_argument("--input",  "-i", type=str, help="Path to input CSV or Excel file")
    parser.add_argument("--output", "-o", type=str, help="Path to save cleaned data")
    parser.add_argument("--output-format", choices=["csv", "xlsx", "json"], default="csv",
                        help="Format for saved data (default: csv)")
    parser.add_argument("--report", "-r", type=str, help="Path to save PDF report")

    # Cleaning
    cg = parser.add_argument_group("Cleaning Options")
    cg.add_argument("--drop-duplicates", action="store_true", help="Remove duplicate rows")
    cg.add_argument("--drop-nulls",      action="store_true", help="Drop rows with null values")
    cg.add_argument("--fill-nulls", choices=["mean","median","mode","zero"],
                    help="Fill null values with strategy")

    # Normalization
    ng = parser.add_argument_group("Normalization Options")
    ng.add_argument("--normalize", choices=["zscore","minmax","robust"],
                    help="Normalization method to apply")
    ng.add_argument("--norm-mean", type=float, default=0.0,
                    help="Target mean for z-score normalization (default: 0.0)")
    ng.add_argument("--norm-std",  type=float, default=1.0,
                    help="Target std for z-score normalization (default: 1.0)")

    # Analysis
    ag = parser.add_argument_group("Analysis Metrics")
    ag.add_argument("--central-tendency", action="store_true", help="Mean, median, mode")
    ag.add_argument("--dispersion",       action="store_true", help="Std dev, variance, IQR, range")
    ag.add_argument("--shape",            action="store_true", help="Skewness & kurtosis")
    ag.add_argument("--correlation",      action="store_true", help="Correlation matrix")
    ag.add_argument("--roc-auc", type=str, metavar="TARGET_COL",
                    help="ROC-AUC vs a binary target column")
    ag.add_argument("--percentiles",  action="store_true", help="P5–P95 percentiles")
    ag.add_argument("--all-metrics",  action="store_true", help="Run all applicable metrics")

    args = parser.parse_args()

    if args.cli:
        if not args.input:
            parser.error("--input is required in CLI mode")
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
