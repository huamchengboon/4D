#!/usr/bin/env python3
"""
Run full data analysis on 4d_history.csv: load, summarize, and generate visualizations.
Saves figures to output/ and prints summary stats.

Usage:
  uv run python -m analysis.run_analysis [--csv PATH]
  uv run python analysis/run_analysis.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Non-interactive backend for scripted runs (no display)
import matplotlib
matplotlib.use("Agg")

# Add project root so "analysis" package is importable
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from analysis.load import load_history, get_draws_long, get_number_frequencies
from analysis.plots import (
    OUTPUT_DIR,
    plot_draws_per_day,
    plot_first_digit_distribution,
    plot_number_frequency_single,
    plot_operator_breakdown,
    plot_prize_type_breakdown,
)


def main(csv_path: Path | None = None) -> None:
    csv_path = csv_path or _root / "4d_history.csv"
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    print("Loading data...")
    df = load_history(csv_path)
    print(f"  Rows: {df.height:,}  Columns: {df.width}")

    # Summary stats
    print("\n--- Summary ---")
    print(df.describe())
    print("\nDate range:", df["date"].min(), "to", df["date"].max())
    print("\nOperators:", df["operator"].unique().to_list())

    # Long format for frequency and digit analysis
    long_df = get_draws_long(df)
    print(f"\nLong format: {long_df.height:,} number records")

    freq = get_number_frequencies(df)
    print(f"\nTop 10 most drawn numbers:\n{freq.head(10)}")

    # Plots (save to output/, no interactive show so script exits cleanly)
    print("\nGenerating plots in output/ ...")
    plot_draws_per_day(df, save=OUTPUT_DIR / "draws_per_day.png")
    plot_operator_breakdown(df, save=OUTPUT_DIR / "operator_breakdown.png")
    plot_number_frequency_single(freq, top_n=30, save=OUTPUT_DIR / "number_frequency.png")
    plot_first_digit_distribution(long_df, save=OUTPUT_DIR / "first_digit_dist.png")
    plot_prize_type_breakdown(long_df, save=OUTPUT_DIR / "prize_type_breakdown.png")
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 4D history data analysis and save plots.")
    parser.add_argument("--csv", type=Path, default=None, help="Path to 4d_history.csv")
    args = parser.parse_args()
    main(csv_path=args.csv)
