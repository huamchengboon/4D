#!/usr/bin/env python3
"""
Hyperparameter tuning for the RL policy using Optuna.
Maximizes final-eval profit (RM) over a search space of lr, entropy, baseline, hidden sizes, seq_len.

Usage:
  uv run python -m analysis.run_rl_tune --trials 20 --max-draws 2000
  uv run python -m analysis.run_rl_tune --trials 10 --epochs 2 --quiet
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import optuna
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from analysis.load import get_draws_as_sets, get_draws_with_prizes, load_history
from analysis.prizes import compute_profit_loss
from analysis.rl import run_rl_backtest


def objective(
    trial: optuna.Trial,
    draws: list,
    draws_with_prizes: list[dict],
    epochs: int,
    device: str | None,
    verbose: bool,
) -> float:
    """Single Optuna trial: train with suggested params, return final-eval profit (to maximize)."""
    lr = trial.suggest_float("lr", 1e-4, 1e-2, log=True)
    entropy_coef = trial.suggest_float("entropy_coef", 0.005, 0.05)
    baseline_ema = trial.suggest_float("baseline_ema", 0.95, 0.999)
    recency_decay = trial.suggest_float("recency_decay", 0.0, 0.02)
    hidden_str = trial.suggest_categorical("hidden", ["256,256", "512,256,256", "512,512,256", "768,384,256"])
    hidden_sizes = tuple(int(x.strip()) for x in hidden_str.split(","))
    seq_len = trial.suggest_categorical("seq_len", [0, 24, 32])
    seq_dim = trial.suggest_categorical("seq_dim", [64, 128]) if seq_len > 0 else 128

    results, _ = run_rl_backtest(
        csv_path=None,
        draws=draws,
        epochs=epochs,
        k=23,
        lr=lr,
        device=device,
        max_draws=None,
        verbose=verbose,
        log_every=999_999,
        checkpoint_path=None,
        resume_from=None,
        save_after_each_epoch=False,
        reward_mode="prize",
        baseline_ema=baseline_ema,
        entropy_coef=entropy_coef,
        recency_decay=recency_decay,
        seq_len=seq_len,
        seq_dim=seq_dim,
        draws_with_prizes=draws_with_prizes,
        hidden_sizes=hidden_sizes,
    )

    prize_slice = draws_with_prizes[: len(results)]
    _, _, total_profit = compute_profit_loss(results, prize_slice, bet_per_number=1.0)
    return float(total_profit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hyperparameter tuning for RL policy (Optuna).")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--trials", type=int, default=20, help="Number of Optuna trials")
    parser.add_argument("--max-draws", type=int, default=2000, help="Cap draws per trial for speed")
    parser.add_argument("--epochs", type=int, default=2, help="Epochs per trial")
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--quiet", action="store_true", help="Suppress per-trial logs")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--study-name", type=str, default="rl_4d")
    parser.add_argument("--save-best", type=Path, default=None, help="Save best params to JSON")
    args = parser.parse_args()

    console = Console()
    csv_path = args.csv or _root / "4d_history.csv"
    if not csv_path.is_file():
        console.print(f"[red]CSV not found:[/] {csv_path}")
        sys.exit(1)

    console.print(Panel("[bold]RL hyperparameter tuning[/] — maximize final-eval profit (RM)", title="Tune", border_style="cyan"))
    console.print(f"Trials: {args.trials}  |  Max draws: {args.max_draws}  |  Epochs/trial: {args.epochs}\n")

    with console.status("[bold green]Loading data..."):
        df = load_history(str(csv_path))
        draws = get_draws_as_sets(df)
        draws_with_prizes = get_draws_with_prizes(df)
    if args.max_draws and len(draws) > args.max_draws:
        draws = draws[: args.max_draws]
        draws_with_prizes = draws_with_prizes[: args.max_draws]
    console.print(f"Loaded [bold]{len(draws)}[/] draws.\n")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", study_name=args.study_name, sampler=optuna.samplers.TPESampler(seed=args.seed, n_startup_trials=5))
    study.optimize(
        lambda t: objective(t, draws, draws_with_prizes, args.epochs, args.device, verbose=not args.quiet),
        n_trials=args.trials,
        show_progress_bar=True,
    )

    console.print("\n[bold green]Best trial[/]")
    best = study.best_trial
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")
    table.add_row("Profit (RM)", f"{best.value:+,.0f}")
    for k, v in best.params.items():
        table.add_row(k, str(v))
    console.print(table)

    if args.save_best:
        args.save_best.parent.mkdir(parents=True, exist_ok=True)
        with open(args.save_best, "w") as f:
            json.dump(best.params, f, indent=2)
        console.print(f"\nBest params saved to [bold]{args.save_best}[/]")

    console.print("\n[dim]Rerun with best params manually, e.g.:[/]")
    lr = best.params["lr"]
    entropy = best.params["entropy_coef"]
    baseline = best.params["baseline_ema"]
    recency = best.params.get("recency_decay", 0.0)
    hidden = best.params["hidden"]
    seq_len = best.params["seq_len"]
    seq_dim = best.params.get("seq_dim", 128)
    cmd = f"uv run python -m analysis.run_rl --lr {lr} --entropy {entropy} --baseline-ema {baseline} --recency-decay {recency} --hidden {hidden}"
    if seq_len > 0:
        cmd += f" --seq-len {seq_len} --seq-dim {seq_dim}"
    console.print(f"  [bold]{cmd}[/]\n")


if __name__ == "__main__":
    main()
