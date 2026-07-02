#!/usr/bin/env python3
"""
Stat Chat - A Python Data Analysis & Cleaning Tool
Supports both GUI (Tkinter) and CLI modes.
"""

import argparse
import sys
from pathlib import Path


def run_gui():
    """Launch the Tkinter GUI application."""
    try:
        import tkinter as tk
        from gui.app import StatChatApp
        root = tk.Tk()
        app = StatChatApp(root)
        root.mainloop()
    except ImportError as e:
        print(f"[ERROR] Could not launch GUI: {e}")
        print("Try running in CLI mode: python main.py --cli --help")
        sys.exit(1)


def run_cli(args):
    """Run the application in CLI mode."""
    from cli.runner import CLIRunner
    runner = CLIRunner(args)
    runner.run()


def main():
    parser = argparse.ArgumentParser(
        prog="Stat Chat",
        description="Data Cleaning, Normalization & Statistical Analysis Tool",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (no GUI)")
    parser.add_argument("--input", "-i", type=str, help="Path to input CSV or Excel file")
    parser.add_argument("--output", "-o", type=str, help="Path to save cleaned data")
    parser.add_argument("--output-format", choices=["csv", "xlsx", "json"], default="csv",
                        help="Format for saved data (default: csv)")
    parser.add_argument("--report", "-r", type=str, help="Path to save PDF report")

    # Cleaning options
    clean_group = parser.add_argument_group("Cleaning Options")
    clean_group.add_argument("--drop-duplicates", action="store_true", help="Remove duplicate rows")
    clean_group.add_argument("--drop-nulls", action="store_true", help="Drop rows with null values")
    clean_group.add_argument("--fill-nulls", choices=["mean", "median", "mode", "zero"],
                              help="Fill null values with strategy")

    # Normalization options
    norm_group = parser.add_argument_group("Normalization Options")
    norm_group.add_argument("--normalize", choices=["zscore", "minmax", "robust"],
                             help="Normalization method to apply")
    norm_group.add_argument("--norm-mean", type=float, default=0.0,
                             help="Target mean for z-score normalization (default: 0.0)")
    norm_group.add_argument("--norm-std", type=float, default=1.0,
                             help="Target std for z-score normalization (default: 1.0)")

    # Analysis metrics
    analysis_group = parser.add_argument_group("Analysis Metrics")
    analysis_group.add_argument("--central-tendency", action="store_true",
                                 help="Compute mean, median, mode")
    analysis_group.add_argument("--dispersion", action="store_true",
                                 help="Compute variance, std dev, IQR, range")
    analysis_group.add_argument("--shape", action="store_true",
                                 help="Compute skewness and kurtosis")
    analysis_group.add_argument("--correlation", action="store_true",
                                 help="Compute correlation matrix")
    analysis_group.add_argument("--roc-auc", type=str, metavar="TARGET_COL",
                                 help="Compute ROC-AUC (provide binary target column name)")
    analysis_group.add_argument("--percentiles", action="store_true",
                                 help="Compute 25th, 50th, 75th, 90th, 95th percentiles")
    analysis_group.add_argument("--all-metrics", action="store_true",
                                 help="Run all applicable metrics")

    args = parser.parse_args()

    if args.cli:
        if not args.input:
            parser.error("--input is required in CLI mode")
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
