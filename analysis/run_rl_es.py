#!/usr/bin/env python3
"""
Train the 4D policy with Evolution Strategies (ES): gradient-free optimization
by perturbing parameters with noise and updating using reward-weighted average.

Usage:
  uv run python -m analysis.run_rl_es [--csv PATH] [--generations 30] [--workers 8] [--sigma 0.02] [--lr 0.01]
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from analysis.load import get_draws_as_sets, get_draws_with_prizes, load_history
from analysis.prizes import compute_profit_loss
from analysis.rl import get_best_device
from analysis.rl_es import DEFAULT_CHECKPOINT_DIR, run_es_backtest


def configure_loguru(console: Console, verbose: bool) -> None:
    logger.remove()
    if verbose:
        logger.add(
            lambda msg: console.print(msg, end=""),
            format="[dim]{time:HH:mm:ss}[/dim] [bold blue]INFO[/] {message}",
            colorize=False,
        )
    else:
        logger.add(lambda _: None, level="DEBUG")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train 4D policy with Evolution Strategies (gradient-free)."
    )
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--generations", type=int, default=30, help="ES generations (default 30)")
    parser.add_argument("--workers", type=int, default=8, help="Population size per generation (default 8)")
    parser.add_argument("--sigma", type=float, default=0.02, help="Perturbation std (default 0.02)")
    parser.add_argument("--lr", type=float, default=0.01, help="ES learning rate (default 0.01)")
    parser.add_argument("--k", type=int, default=23, help="Numbers to predict per draw (default 23)")
    parser.add_argument("--device", type=str, default=None, help="cuda, mps, or cpu (default: auto)")
    parser.add_argument("--max-draws", type=int, default=None, help="Cap number of draws")
    parser.add_argument("--random-draws", type=int, nargs="?", metavar="SEED", const=-1, default=None, help="With --max-draws, use random subset. No SEED = new random each run; pass SEED (e.g. 42) for reproducibility.")
    parser.add_argument("--reward", type=str, default="prize", choices=("binary", "count", "prize"), help="Fitness = total reward (default: prize)")
    parser.add_argument("--recency-decay", type=float, default=0.0, help="State recency decay (0 = off)")
    parser.add_argument("--seq-len", type=int, default=0, help="Attention over last N draws (0 = off)")
    parser.add_argument("--seq-dim", type=int, default=128, help="Seq embedding dim when --seq-len > 0")
    parser.add_argument("--hidden", type=str, default="512,256,256", help="Hidden layer sizes (comma-separated)")
    parser.add_argument("--prize-weighted-state", action="store_true", help="State = prize-weighted history; use with --reward prize")
    parser.add_argument("--checkpoint", type=Path, default=None, help="Path to save checkpoint (default: output/rl_es_checkpoint.pt)")
    parser.add_argument("--resume", type=Path, default=None, help="Path to checkpoint to resume from")
    parser.add_argument("--no-save", action="store_true", help="Do not save checkpoint")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for ES noise")
    parser.add_argument("--elitist", action="store_true", help="If best worker beats updated mean, keep best worker's params for next gen")
    parser.add_argument("--resample-draws", action="store_true", help="Resample max_draws random draws each generation (reduces overfitting; requires --max-draws)")
    parser.add_argument("--overfit", action="store_true", help="Overfit mode: fixed subset of draws (no resampling). Defaults: max-draws=200, random seed 42, 80 generations.")
    parser.add_argument("--quiet", action="store_true", help="Less output")
    args = parser.parse_args()

    # Overfit mode: fixed draws, no resampling, sensible defaults
    if args.overfit:
        if args.max_draws is None:
            args.max_draws = 200
        if args.random_draws is None:
            args.random_draws = 42  # fixed seed so same 200 draws every run
        if args.generations == 30:  # default
            args.generations = 80
        args.resample_draws = False  # never resample when overfitting

    random_draws_seed: int | None = None
    if args.random_draws is not None:
        random_draws_seed = random.randint(0, 2**31 - 1) if args.random_draws == -1 else args.random_draws

    console = Console()
    verbose = not args.quiet
    configure_loguru(console, verbose)

    if args.resample_draws and not args.max_draws:
        console.print("[red]--resample-draws requires --max-draws (e.g. --max-draws 365)[/]")
        sys.exit(1)

    csv_path = args.csv or _root / "4d_history.csv"
    if not csv_path.is_file():
        console.print(f"[red]CSV not found:[/] {csv_path}")
        sys.exit(1)

    checkpoint_path = (args.checkpoint or DEFAULT_CHECKPOINT_DIR / "rl_es_checkpoint.pt") if not args.no_save else None

    title = "[bold cyan]Run RL (ES)[/]"
    if args.overfit:
        title = "[bold yellow]Run RL (ES) — Overfit mode[/]"
    console.print(
        Panel(
            "[bold]4D Evolution Strategies[/] — Gradient-free policy training." + (" [overfit: fixed draws]" if args.overfit else ""),
            title=title,
            border_style="yellow" if args.overfit else "cyan",
        )
    )
    config_table = Table(show_header=False, box=None, padding=(0, 2))
    config_table.add_column(style="dim")
    config_table.add_column()
    resolved_device = args.device if args.device else str(get_best_device())
    config_table.add_row("CSV", str(csv_path))
    config_table.add_row("Generations", str(args.generations))
    config_table.add_row("Workers", str(args.workers))
    config_table.add_row("Sigma", str(args.sigma))
    config_table.add_row("LR", str(args.lr))
    config_table.add_row("K (picks)", str(args.k))
    config_table.add_row("Device", f"[bold green]{resolved_device}[/]" if resolved_device != "cpu" else resolved_device)
    if args.max_draws:
        if random_draws_seed is not None:
            config_table.add_row("Max draws", f"{args.max_draws} (random, seed={random_draws_seed})")
        else:
            config_table.add_row("Max draws", f"{args.max_draws} (first N)")
    config_table.add_row("Reward", args.reward)
    config_table.add_row("Checkpoint", str(checkpoint_path) if checkpoint_path else "[dim]disabled[/]")
    if args.resume:
        config_table.add_row("Resume from", str(args.resume))
    config_table.add_row("Hidden", args.hidden)
    if args.recency_decay > 0:
        config_table.add_row("Recency decay", str(args.recency_decay))
    if args.seq_len > 0:
        config_table.add_row("Seq (attention)", f"last {args.seq_len} (dim={args.seq_dim})")
    if args.elitist:
        config_table.add_row("Elitist", "on (keep best worker when it beats mean)")
    if args.resample_draws:
        config_table.add_row("Resample draws", "each gen (anti-overfit)" + ("" if args.max_draws else " [requires --max-draws]"))
    if args.overfit:
        config_table.add_row("Mode", "[bold yellow]Overfit[/] (fixed draws, no resampling)")
    console.print(config_table)
    console.print()

    with console.status("[bold green]Loading draws...", spinner="dots"):
        df = load_history(str(csv_path))
        draws = get_draws_as_sets(df)
        draws_with_prizes = get_draws_with_prizes(df) if (args.reward == "prize" or args.prize_weighted_state) else None
    console.print(f"[green]Loaded[/] [bold]{len(draws)}[/] draws.\n")

    hidden_sizes = tuple(int(x.strip()) for x in args.hidden.split(",") if x.strip())
    if not hidden_sizes:
        hidden_sizes = (512, 256, 256)

    results, _ = run_es_backtest(
        csv_path=None,
        draws=draws,
        draws_with_prizes=draws_with_prizes,
        generations=args.generations,
        n_workers=args.workers,
        sigma=args.sigma,
        lr=args.lr,
        k=args.k,
        device=args.device,
        max_draws=args.max_draws,
        random_draws_seed=random_draws_seed,
        reward_mode=args.reward,
        recency_decay=args.recency_decay,
        seq_len=args.seq_len,
        seq_dim=args.seq_dim,
        hidden_sizes=hidden_sizes,
        prize_weighted_state=args.prize_weighted_state,
        checkpoint_path=checkpoint_path,
        resume_from=args.resume,
        save_after_each_gen=True,
        verbose=verbose,
        seed=args.seed,
        elitist=args.elitist,
        resample_draws_each_gen=args.resample_draws,
    )

    hits = sum(1 for r in results if r.hit)
    total = len(results)
    hit_rate = hits / total if total else 0
    draws_with_prizes_pl = get_draws_with_prizes(df)[: len(results)]
    total_cost_rm, total_winnings_rm, total_profit_rm = compute_profit_loss(
        results, draws_with_prizes_pl, bet_per_number=1.0
    )

    summary = Table(title="ES final", box=None, show_header=False, padding=(0, 2))
    summary.add_column(style="dim")
    summary.add_column(style="bold")
    summary.add_row("Hits", f"{hits}/{total}")
    summary.add_row("Hit rate", f"{hit_rate:.4f}")
    summary.add_row("Cost (RM)", f"{total_cost_rm:,.0f}")
    summary.add_row("Winnings (RM)", f"{total_winnings_rm:,.0f}")
    profit_style = "green" if total_profit_rm >= 0 else "red"
    summary.add_row("Profit / Loss (RM)", f"[{profit_style}]{total_profit_rm:+,.0f}[/]")
    console.print(Panel(summary, title="[bold green]Done[/]", border_style="green"))
    console.print()


if __name__ == "__main__":
    main()
