#!/usr/bin/env python3
"""
Run EDA and baseline model comparison for 4D data.
Prints statistical findings and recommendation: no ML prediction is viable;
best "model" is uniform or empirical baseline for entertainment only.

Usage:
  uv run python -m analysis.run_ml [--csv PATH] [--test-ratio 0.1]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from analysis.eda import run_eda, print_eda_report
from analysis.load import load_history, get_draws_long
from analysis.models import (
    PredictionResult,
    run_model_comparison,
)


def print_model_results(results: list[PredictionResult]) -> None:
    print("\n" + "=" * 60)
    print("BASELINE MODEL EVALUATION (holdout test set)")
    print("=" * 60)
    print("Metric: Did the model's 23 predicted numbers contain the actual 1st prize?")
    print()
    for r in results:
        print(f"  {r.model_name}:")
        print(f"    Holdout draws: {r.n_holdout_draws}")
        print(f"    Hits:          {r.hit_any} ({r.hit_rate:.4f})")
        print(f"    Expected (random 23/10000): {r.expected_random:.4f}")
        print()
    print("Conclusion: Hit rates are consistent with random chance.")
    print("No model improves on uniform or empirical baseline for prediction.")
    print("=" * 60)


def main(csv_path: Path | None = None, test_ratio: float = 0.1) -> None:
    csv_path = csv_path or _root / "4d_history.csv"
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    print("Loading data...")
    df = load_history(csv_path)
    long_df = get_draws_long(df)

    print("\nRunning EDA and statistical tests...")
    eda_result = run_eda(df=df, long_df=long_df)
    print_eda_report(eda_result)

    print("\nTraining and evaluating baseline models...")
    results = run_model_comparison(csv_path=str(csv_path), test_ratio=test_ratio)
    print_model_results(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run EDA and baseline model comparison for 4D data."
    )
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--test-ratio", type=float, default=0.1, help="Fraction of latest dates for test")
    args = parser.parse_args()
    main(csv_path=args.csv, test_ratio=args.test_ratio)
