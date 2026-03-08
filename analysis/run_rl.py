#!/usr/bin/env python3
"""
Train the RL policy on full history (reward when any predicted number hits, punish when none).
Backtest over the whole dataset.

Usage:
  uv run python -m analysis.run_rl [--csv PATH] [--epochs 3] [--k 23]
"""

from __future__ import annotations

import argparse
import random
import sys
import threading
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
from analysis.rl import (
    DEFAULT_CHECKPOINT_DIR,
    get_best_device,
    run_final_eval,
    run_rl_backtest,
)
from analysis.training_chart import create_chart_window, keep_chart_open

try:
    from matplotlib import pyplot as plt
except Exception:
    plt = None


def configure_loguru(console: Console, verbose: bool) -> None:
    """Send loguru output through Rich console with a clean format."""
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
        description="Train RL policy on 4D history: reward hit, punish miss; backtest over full history."
    )
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--epochs", type=int, default=3, help="Passes over full history")
    parser.add_argument("--k", type=int, default=23, help="Numbers to predict per draw")
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--device", type=str, default=None, help="Device: cuda, mps (Apple Silicon), or cpu (default: auto)")
    parser.add_argument("--max-draws", type=int, default=None, help="Cap draws (default: first N in dataset order; use --random-draws for random subset)")
    parser.add_argument("--random-draws", type=int, nargs="?", metavar="SEED", const=-1, default=None, help="With --max-draws, use a random subset. No SEED = new random each run; pass SEED (e.g. 42) for reproducibility.")
    parser.add_argument("--quiet", action="store_true", help="Less output (no per-step logs)")
    parser.add_argument("--log-every", type=int, default=500, help="Print progress every N steps (default 500)")
    parser.add_argument("--checkpoint", type=Path, default=None, help="Path to save checkpoint (default: output/rl_checkpoint.pt)")
    parser.add_argument("--resume", type=Path, default=None, help="Path to checkpoint to load; training continues from next epoch")
    parser.add_argument("--no-save", action="store_true", help="Do not save checkpoint (overrides --checkpoint)")
    parser.add_argument("--reward", type=str, default="prize", choices=("binary", "count", "prize"), help="Reward: binary (+1/-1), count (n_hits), or prize (RM winnings - cost, aligns with profit). Default: prize")
    parser.add_argument("--entropy", type=float, default=0.01, help="Entropy bonus coef for exploration (default 0.01)")
    parser.add_argument("--baseline-ema", type=float, default=0.99, help="EMA for running baseline, variance reduction (default 0.99)")
    parser.add_argument("--recency-decay", type=float, default=0.0, help="Decay in (0,1) to weight recent draws more (default 0 = off)")
    parser.add_argument("--seq-len", type=int, default=0, help="Attention over last N draws (0 = off). Model sees time-series of past results.")
    parser.add_argument("--seq-dim", type=int, default=128, help="Attention embedding dim when --seq-len > 0 (default 128)")
    parser.add_argument("--hidden", type=str, default="512,256,256", help="Hidden layer sizes, comma-separated (default 512,256,256)")
    parser.add_argument("--forever", action="store_true", help="Run until Ctrl+C; then run final eval and show summary only")
    parser.add_argument("--no-chart", action="store_true", help="Disable pop-up training chart window")
    parser.add_argument("--prize-weighted-state", action="store_true", help="State = prize-weighted history (1st=2500, 2nd=1000, …); needs prize data, use with --reward prize")
    parser.add_argument("--overfit", action="store_true", help="Overfit mode: train on a fixed small subset. Defaults: max-draws=200, random seed 42, 50 epochs.")
    args = parser.parse_args()

    # Overfit mode: fixed subset, more epochs
    if args.overfit:
        if args.max_draws is None:
            args.max_draws = 200
        if args.random_draws is None:
            args.random_draws = 42
        if args.epochs == 3 and not args.forever:
            args.epochs = 50

    # Resolve random-draws: None = off, -1 = random seed each run, else use given SEED
    random_draws_seed: int | None = None
    if args.random_draws is not None:
        random_draws_seed = random.randint(0, 2**31 - 1) if args.random_draws == -1 else args.random_draws

    console = Console()
    verbose = not args.quiet
    configure_loguru(console, verbose)

    csv_path = args.csv or _root / "4d_history.csv"
    if not csv_path.is_file():
        console.print(f"[red]CSV not found:[/] {csv_path}")
        sys.exit(1)

    checkpoint_path = (args.checkpoint or DEFAULT_CHECKPOINT_DIR / "rl_checkpoint.pt") if (not args.no_save or args.forever) else None

    # Header
    title = "[bold cyan]Run RL[/]"
    if args.overfit:
        title = "[bold yellow]Run RL — Overfit mode[/]"
    console.print(
        Panel(
            "[bold]4D RL Backtest[/] — Reward hit, punish miss; train over full history." + (" [overfit: fixed draws]" if args.overfit else ""),
            title=title,
            border_style="yellow" if args.overfit else "cyan",
        )
    )

    # Config table
    config_table = Table(show_header=False, box=None, padding=(0, 2))
    config_table.add_column(style="dim")
    config_table.add_column()
    resolved_device = args.device if args.device is not None else str(get_best_device())
    config_table.add_row("CSV", str(csv_path))
    config_table.add_row("Epochs", "∞ (until Ctrl+C)" if args.forever else str(args.epochs))
    config_table.add_row("K (picks)", str(args.k))
    config_table.add_row("Device", f"[bold green]{resolved_device}[/]" if resolved_device != "cpu" else resolved_device)
    if args.max_draws is not None:
        if random_draws_seed is not None:
            config_table.add_row("Max draws", f"{args.max_draws} (random, seed={random_draws_seed})")
        else:
            config_table.add_row("Max draws", f"{args.max_draws} (first N)")
    config_table.add_row("Checkpoint", str(checkpoint_path) if checkpoint_path else "[dim]disabled (--no-save)[/]")
    if args.resume:
        config_table.add_row("Resume from", str(args.resume))
    config_table.add_row("Reward", args.reward)
    if args.overfit:
        config_table.add_row("Mode", "[bold yellow]Overfit[/] (fixed subset, more epochs)")
    config_table.add_row("Hidden", args.hidden)
    config_table.add_row("Entropy coef", str(args.entropy))
    if args.recency_decay > 0:
        config_table.add_row("Recency decay", str(args.recency_decay))
    if args.seq_len > 0:
        config_table.add_row("Attention (seq)", f"last {args.seq_len} draws (dim={args.seq_dim})")
    console.print(config_table)
    console.print()

    # Load data with spinner
    with console.status("[bold green]Loading draws...", spinner="dots"):
        df = load_history(str(csv_path))
        draws = get_draws_as_sets(df)
        draws_with_prizes = get_draws_with_prizes(df) if (args.reward == "prize" or args.prize_weighted_state) else None
    console.print(f"[green]Loaded[/] [bold]{len(draws)}[/] draws.\n")

    hidden_sizes = tuple(int(x.strip()) for x in args.hidden.split(",") if x.strip())
    if not hidden_sizes:
        hidden_sizes = (512, 256, 256)

    chart_enabled = verbose and not args.no_chart
    step_callback = None
    chart_fig = None
    training_done = threading.Event()
    stop_event = threading.Event()
    result_holder: list = []

    if chart_enabled and plt is not None:
        chart_fig, update_chart, step_callback = create_chart_window()
        if args.forever:
            console.print("[dim]Training until Ctrl+C. Final eval after you interrupt.[/]\n")

        def run_training_thread() -> None:
            try:
                if args.forever:
                    prize_slice = draws_with_prizes[: len(draws)] if draws_with_prizes else None
                    epoch_num = 0
                    resume_from = args.resume
                    while not stop_event.is_set():
                        epoch_num += 1
                        results_ep, _ = run_rl_backtest(
                            csv_path=None,
                            draws=draws,
                            epochs=epoch_num,
                            k=args.k,
                            lr=args.lr,
                            device=args.device,
                            max_draws=args.max_draws,
                            verbose=verbose,
                            log_every=args.log_every,
                            checkpoint_path=checkpoint_path,
                            resume_from=resume_from,
                            save_after_each_epoch=True,
                            reward_mode=args.reward,
                            baseline_ema=args.baseline_ema,
                            entropy_coef=args.entropy,
                            recency_decay=args.recency_decay,
                            seq_len=args.seq_len,
                            seq_dim=args.seq_dim,
                            draws_with_prizes=draws_with_prizes,
                            prize_weighted_state=args.prize_weighted_state,
                            hidden_sizes=hidden_sizes,
                            skip_final_eval=True,
                            random_draws_seed=random_draws_seed,
                            on_step_callback=step_callback,
                        )
                        resume_from = checkpoint_path
                        console.print(f"[dim]Epoch {epoch_num} done — {sum(1 for r in results_ep if r.hit)}/{len(results_ep)} hits[/]")
                    if checkpoint_path.exists():
                        results = run_final_eval(
                            checkpoint_path,
                            draws,
                            k=args.k,
                            device=args.device,
                            hidden_sizes=hidden_sizes,
                            seq_len=args.seq_len,
                            seq_dim=args.seq_dim,
                            recency_decay=args.recency_decay,
                            draws_with_prizes=prize_slice,
                            prize_weighted_state=args.prize_weighted_state,
                        )
                        result_holder.append(results)
                else:
                    results, policy = run_rl_backtest(
                        csv_path=None,
                        draws=draws,
                        epochs=args.epochs,
                        k=args.k,
                        lr=args.lr,
                        device=args.device,
                        max_draws=args.max_draws,
                        verbose=verbose,
                        log_every=args.log_every,
                        checkpoint_path=checkpoint_path,
                        resume_from=args.resume,
                        save_after_each_epoch=True,
                        reward_mode=args.reward,
                        baseline_ema=args.baseline_ema,
                        entropy_coef=args.entropy,
                        recency_decay=args.recency_decay,
                        seq_len=args.seq_len,
                        seq_dim=args.seq_dim,
                        draws_with_prizes=draws_with_prizes,
                        prize_weighted_state=args.prize_weighted_state,
                        hidden_sizes=hidden_sizes,
                        random_draws_seed=random_draws_seed,
                        on_step_callback=step_callback,
                    )
                    result_holder.append((results, policy))
            finally:
                training_done.set()

        thread = threading.Thread(target=run_training_thread, daemon=False)
        thread.start()
        try:
            while not training_done.is_set():
                update_chart()
                plt.pause(0.05)
        except KeyboardInterrupt:
            stop_event.set()
            console.print("\n[bold yellow]Interrupted. Waiting for epoch to finish...[/]\n")
        thread.join()
        if not result_holder:
            console.print("[yellow]No results (interrupted before completion).[/]")
            return
        if args.forever:
            results = result_holder[0]
        else:
            results, _ = result_holder[0]
        keep_chart_open(chart_fig)
        # Summary
        if chart_enabled:
            hits = sum(1 for r in results if r.hit)
            total = len(results)
            hit_rate = hits / total if total else 0
            draws_with_prizes_for_pl = get_draws_with_prizes(df)[: len(results)]
            total_cost_rm, total_winnings_rm, total_profit_rm = compute_profit_loss(
                results, draws_with_prizes_for_pl, bet_per_number=1.0
            )
            summary = Table(title="Final pass", box=None, show_header=False, padding=(0, 2))
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
            return
    else:
        step_callback = None

    try:
        if args.forever:
            # Run until Ctrl+C; then run final eval and show summary only
            prize_slice = draws_with_prizes[: len(draws)] if draws_with_prizes else None
            console.print("[dim]Training until Ctrl+C. Final eval will run when you interrupt.[/]\n")
            epoch_num = 0
            resume_from = args.resume
            try:
                while True:
                    epoch_num += 1
                    results_ep, _ = run_rl_backtest(
                        csv_path=None,
                        draws=draws,
                        epochs=epoch_num,
                        k=args.k,
                        lr=args.lr,
                        device=args.device,
                        max_draws=args.max_draws,
                        verbose=verbose,
                        log_every=args.log_every,
                        checkpoint_path=checkpoint_path,
                        resume_from=resume_from,
                        save_after_each_epoch=True,
                        reward_mode=args.reward,
                        baseline_ema=args.baseline_ema,
                        entropy_coef=args.entropy,
                        recency_decay=args.recency_decay,
                        seq_len=args.seq_len,
                        seq_dim=args.seq_dim,
                        draws_with_prizes=draws_with_prizes,
                        prize_weighted_state=args.prize_weighted_state,
                        hidden_sizes=hidden_sizes,
                        skip_final_eval=True,
                        random_draws_seed=random_draws_seed,
                        on_step_callback=step_callback,
                    )
                    resume_from = checkpoint_path
                    hits_ep = sum(1 for r in results_ep if r.hit)
                    n_ep = len(results_ep)
                    console.print(f"[dim]Epoch {epoch_num} done — {hits_ep}/{n_ep} hits (rate {hits_ep / n_ep:.4f})[/]")
            except KeyboardInterrupt:
                console.print("\n[bold yellow]Interrupted. Running final eval...[/]\n")
            if not checkpoint_path.exists():
                console.print("[red]No checkpoint yet (interrupted before first epoch).[/]")
                sys.exit(1)
            try:
                results = run_final_eval(
                    checkpoint_path,
                    draws,
                    k=args.k,
                    device=args.device,
                    hidden_sizes=hidden_sizes,
                    seq_len=args.seq_len,
                    seq_dim=args.seq_dim,
                    recency_decay=args.recency_decay,
                    draws_with_prizes=prize_slice,
                    prize_weighted_state=args.prize_weighted_state,
                )
            except KeyboardInterrupt:
                console.print("[yellow]Final eval interrupted. No summary.[/]")
                sys.exit(0)
        else:
            # Train
            results, policy = run_rl_backtest(
                csv_path=None,
                draws=draws,
                epochs=args.epochs,
                k=args.k,
                lr=args.lr,
                device=args.device,
                max_draws=args.max_draws,
                verbose=verbose,
                log_every=args.log_every,
                checkpoint_path=checkpoint_path,
                resume_from=args.resume,
                save_after_each_epoch=True,
                reward_mode=args.reward,
                baseline_ema=args.baseline_ema,
                entropy_coef=args.entropy,
                recency_decay=args.recency_decay,
                seq_len=args.seq_len,
                seq_dim=args.seq_dim,
                draws_with_prizes=draws_with_prizes,
                prize_weighted_state=args.prize_weighted_state,
                hidden_sizes=hidden_sizes,
                random_draws_seed=random_draws_seed,
                on_step_callback=step_callback,
            )
    finally:
        if chart_fig is not None:
            keep_chart_open(chart_fig)

    hits = sum(1 for r in results if r.hit)
    total = len(results)
    hit_rate = hits / total if total else 0

    # P&L: RM1 per number (23 numbers × RM1 = RM23 per draw)
    draws_with_prizes_for_pl = get_draws_with_prizes(df)[: len(results)]
    total_cost_rm, total_winnings_rm, total_profit_rm = compute_profit_loss(
        results, draws_with_prizes_for_pl, bet_per_number=1.0
    )

    # Final summary table
    summary = Table(title="Final pass", box=None, show_header=False, padding=(0, 2))
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
