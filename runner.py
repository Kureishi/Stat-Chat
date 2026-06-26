"""CLI mode runner."""

import sys
from pathlib import Path
from core.loader import load_file, save_file, get_file_info
from core.cleaner import apply_cleaning, apply_normalization
from core.analyzer import run_analysis
from core.reporter import generate_report


class CLIRunner:
    def __init__(self, args):
        self.args = args

    def run(self):
        args = self.args
        print(f"\n── DataLyzer CLI ──────────────────────────────────")
        print(f"Loading: {args.input}")

        try:
            original_df = load_file(args.input)
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

        info = get_file_info(original_df)
        print(f"  Rows: {info['rows']}  |  Columns: {info['columns']}")
        print(f"  Numeric cols: {info['numeric_columns']}")

        # Cleaning
        clean_opts = {
            "drop_duplicates": args.drop_duplicates,
            "drop_nulls": args.drop_nulls,
            "fill_nulls": args.fill_nulls,
        }
        cleaned_df, clean_log = apply_cleaning(original_df.copy(), clean_opts)
        for msg in clean_log:
            print(f"  [clean] {msg}")

        # Normalization
        norm_opts = {
            "normalize": args.normalize,
            "norm_mean": args.norm_mean,
            "norm_std": args.norm_std,
        }
        cleaned_df, norm_log = apply_normalization(cleaned_df, norm_opts)
        for msg in norm_log:
            print(f"  [norm]  {msg}")

        # Save cleaned data
        if args.output:
            out_path = save_file(cleaned_df, args.output, fmt=args.output_format)
            print(f"  [saved] Cleaned data → {out_path}")

        # Analysis
        analysis_opts = {
            "central_tendency": args.central_tendency,
            "dispersion": args.dispersion,
            "shape": args.shape,
            "correlation": args.correlation,
            "percentiles": args.percentiles,
            "normality": False,
            "roc_auc": args.roc_auc,
            "all_metrics": args.all_metrics,
        }
        results = run_analysis(cleaned_df, analysis_opts)

        if results:
            print(f"\n── Analysis Results ───────────────────────────────")
            for section, data in results.items():
                if section == "error":
                    print(f"  [error] {data}")
                elif section == "correlation":
                    print(f"  [correlation] Matrix computed ({len(data.columns)} x {len(data.columns)})")
                elif section == "roc_auc":
                    for col, v in data.items():
                        if "auc" in v:
                            print(f"  [roc_auc] {col}: AUC = {v['auc']:.4f}")
                        elif "error" in v:
                            print(f"  [roc_auc] {col}: ERROR - {v['error']}")
                else:
                    print(f"\n  [{section}]")
                    for col, vals in data.items():
                        summary = "  ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                                            for k, v in vals.items())
                        print(f"    {col}: {summary}")

        # Report
        if args.report:
            print(f"\n── Generating PDF Report ──────────────────────────")
            try:
                out = generate_report(
                    filepath=args.report,
                    original_df=original_df,
                    cleaned_df=cleaned_df,
                    analysis_results=results,
                    clean_log=clean_log,
                    norm_log=norm_log,
                    source_file=args.input,
                )
                print(f"  [saved] Report → {out}")
            except Exception as e:
                print(f"  [ERROR] Could not generate report: {e}")

        print("\n── Done ───────────────────────────────────────────\n")
