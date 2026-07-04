"""CLI mode runner."""

import sys
import base64
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
        print(f"\n── Stat Chat CLI ──────────────────────────────────")
        print(f"Loading: {args.input}")

        try:
            original_df = load_file(args.input)
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

        info = get_file_info(original_df)
        print(f"  Rows: {info['rows']}  |  Columns: {info['columns']}")
        print(f"  Numeric cols: {info['numeric_columns']}")

        # ── Configure LLM backend ─────────────────────────────────────────────
        if args.adjust or args.adjust_image:
            from core.llm_backend import LLMConfig, set_config
            provider = getattr(args, "backend", "claude")
            cfg = LLMConfig(
                provider=provider,
                lmstudio_base_url=getattr(args, "lmstudio_url", "http://localhost:1234"),
                lmstudio_model=getattr(args, "lmstudio_model", ""),
                lmstudio_vision_model=getattr(args, "lmstudio_vision_model", ""),
            )
            set_config(cfg)
            print(f"  [backend] {provider}"
                  + (f" @ {cfg.lmstudio_base_url}" if "lmstudio" in provider else ""))

        # ── Cleaning ──────────────────────────────────────────────────────────
        clean_opts = {
            "drop_duplicates": args.drop_duplicates,
            "drop_nulls":      args.drop_nulls,
            "fill_nulls":      args.fill_nulls,
        }
        cleaned_df, clean_log = apply_cleaning(original_df.copy(), clean_opts)
        for msg in clean_log:
            print(f"  [clean] {msg}")

        # ── Normalization ─────────────────────────────────────────────────────
        norm_opts = {
            "normalize": args.normalize,
            "norm_mean": args.norm_mean,
            "norm_std":  args.norm_std,
        }
        cleaned_df, norm_log = apply_normalization(cleaned_df, norm_opts)
        for msg in norm_log:
            print(f"  [norm]  {msg}")

        # ── Text adjustments ──────────────────────────────────────────────────
        adj_history = []
        working_df  = cleaned_df.copy()

        if args.adjust:
            from core.adjuster import apply_instructions
            import datetime
            print(f"\n── Applying Text Adjustments ──────────────────────")
            for instruction in args.adjust:
                print(f"  Instruction: \"{instruction}\"")
                try:
                    working_df, descriptions, ops = apply_instructions(working_df, instruction)
                    for d in descriptions:
                        print(f"  [adjust] {d}")
                    adj_history.append({
                        "version":     len(adj_history) + 1,
                        "df":          working_df.copy(),
                        "description": "; ".join(descriptions),
                        "ops":         ops,
                        "timestamp":   datetime.datetime.now().strftime("%H:%M:%S"),
                    })
                except Exception as e:
                    print(f"  [ERROR] Could not apply: {e}")
                    sys.exit(1)

        # ── Image annotation ──────────────────────────────────────────────────
        if args.adjust_image:
            from core.adjuster import apply_instructions_from_image
            import datetime
            print(f"\n── Parsing Annotated Image ────────────────────────")
            img_path = Path(args.adjust_image)
            if not img_path.exists():
                print(f"  [ERROR] Image not found: {img_path}")
                sys.exit(1)
            print(f"  Image: {img_path.name}")
            try:
                with open(img_path, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode("utf-8")
                working_df, descriptions, ops = apply_instructions_from_image(
                    working_df, image_b64
                )
                for d in descriptions:
                    print(f"  [adjust] {d}")
                adj_history.append({
                    "version":     len(adj_history) + 1,
                    "df":          working_df.copy(),
                    "description": f"From image '{img_path.name}': " + "; ".join(descriptions),
                    "ops":         ops,
                    "timestamp":   datetime.datetime.now().strftime("%H:%M:%S"),
                })
            except Exception as e:
                print(f"  [ERROR] Could not parse image: {e}")
                sys.exit(1)

        # ── Save output data ──────────────────────────────────────────────────
        final_df = working_df  # post-adjustment (or just cleaned if no adjustments)

        if args.output:
            out_path = save_file(final_df, args.output, fmt=args.output_format)
            print(f"\n  [saved] Data → {out_path}")

        # ── Analysis ─────────────────────────────────────────────────────────
        df_for_analysis = final_df.copy().reset_index(drop=True)
        if args.roc_auc and args.roc_auc in original_df.columns:
            df_for_analysis[args.roc_auc] = original_df[args.roc_auc].reset_index(drop=True)

        analysis_opts = {
            "central_tendency": args.central_tendency,
            "dispersion":       args.dispersion,
            "shape":            args.shape,
            "correlation":      args.correlation,
            "percentiles":      args.percentiles,
            "normality":        False,
            "roc_auc":          args.roc_auc,
            "all_metrics":      args.all_metrics,
            "original_df":      original_df,
        }
        results = run_analysis(df_for_analysis, analysis_opts)

        if results:
            print(f"\n── Analysis Results ───────────────────────────────")
            for section, data in results.items():
                if section == "error":
                    print(f"  [error] {data}")
                elif section == "correlation":
                    print(f"  [correlation] Matrix computed "
                          f"({len(data.columns)} x {len(data.columns)})")
                elif section == "roc_auc":
                    for col, v in data.items():
                        if "auc" in v:
                            print(f"  [roc_auc] {col}: AUC = {v['auc']:.4f}")
                        elif "error" in v:
                            print(f"  [roc_auc] {col}: ERROR - {v['error']}")
                else:
                    print(f"\n  [{section}]")
                    for col, vals in data.items():
                        summary = "  ".join(
                            f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                            for k, v in vals.items()
                        )
                        print(f"    {col}: {summary}")

        # ── PDF Report ────────────────────────────────────────────────────────
        if args.report:
            print(f"\n── Generating PDF Report ──────────────────────────")
            try:
                # Seed history with original if adjustments were made
                full_history = []
                if adj_history:
                    import datetime
                    full_history = [{
                        "version":     0,
                        "df":          original_df.copy(),
                        "description": "Original dataset",
                        "ops":         [],
                        "timestamp":   datetime.datetime.now().strftime("%H:%M:%S"),
                    }] + adj_history

                out = generate_report(
                    filepath=args.report,
                    original_df=original_df,
                    cleaned_df=final_df,
                    analysis_results=results,
                    clean_log=clean_log,
                    norm_log=norm_log,
                    source_file=args.input,
                    adjustment_history=full_history if full_history else None,
                )
                print(f"  [saved] Report → {out}")
            except Exception as e:
                print(f"  [ERROR] Could not generate report: {e}")

        print("\n── Done ───────────────────────────────────────────\n")
