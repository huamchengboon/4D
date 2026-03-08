#!/usr/bin/env python3
"""
Train a Transformer to predict the next 4D draw from a sequence of past draws.
Fast supervised training with BCE loss; eval hit rate and P&L.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from tqdm import tqdm

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from analysis.load import get_draws_as_sets, get_draws_with_prizes, load_history
from analysis.prizes import compute_draw_winnings, compute_profit_loss
from analysis.transformer_4d import (
    N_NUMBERS,
    DrawSequenceDataset,
    NextDrawTransformer,
    predict_top_k,
)

DEFAULT_CHECKPOINT_DIR = _root / "output"


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Transformer for 4D next-draw prediction.")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--seq-len", type=int, default=64, help="Number of past draws as input (default 64)")
    parser.add_argument("--d-model", type=int, default=256, help="Transformer dimension (default 256)")
    parser.add_argument("--nhead", type=int, default=8, help="Attention heads (default 8)")
    parser.add_argument("--layers", type=int, default=4, help="Encoder layers (default 4)")
    parser.add_argument("--dim-ff", type=int, default=1024, help="Feedforward dim (default 1024)")
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--epochs", type=int, default=20, help="Training epochs (default 20)")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size (default 64)")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate (default 3e-4)")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Fraction of data for validation (default 0.1)")
    parser.add_argument("--max-draws", type=int, default=None, help="Cap total draws (for quick runs)")
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--checkpoint", type=Path, default=None, help="Save best model path")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    console = Console()
    verbose = not args.quiet
    if verbose:
        logger.remove()
        logger.add(
            lambda msg: console.print(msg, end=""),
            format="[dim]{time:HH:mm:ss}[/dim] [blue]INFO[/] {message}",
            colorize=False,
        )
    else:
        logger.remove()
        logger.add(lambda _: None, level="DEBUG")

    csv_path = args.csv or _root / "4d_history.csv"
    if not csv_path.is_file():
        console.print(f"[red]CSV not found:[/] {csv_path}")
        sys.exit(1)

    device = torch.device(args.device) if args.device else get_device()
    console.print(Panel("[bold]4D Transformer[/] — Next-draw prediction from past sequence.", title="[bold cyan]Train[/]", border_style="cyan"))
    config = Table(show_header=False, box=None, padding=(0, 2))
    config.add_column(style="dim")
    config.add_column()
    config.add_row("CSV", str(csv_path))
    config.add_row("Seq len", str(args.seq_len))
    config.add_row("d_model", str(args.d_model))
    config.add_row("Layers", str(args.layers))
    config.add_row("Device", str(device))
    config.add_row("Epochs", str(args.epochs))
    config.add_row("Batch size", str(args.batch_size))
    config.add_row("LR", str(args.lr))
    console.print(config)
    console.print()

    df = load_history(str(csv_path))
    draws = get_draws_as_sets(df)
    draws_with_prizes = get_draws_with_prizes(df)
    if args.max_draws is not None and args.max_draws < len(draws):
        draws = draws[: args.max_draws]
        draws_with_prizes = draws_with_prizes[: len(draws)]
    n = len(draws)
    if n < 2 * (args.seq_len + 1):
        console.print("[red]Not enough draws (need at least 2*(seq_len+1)).[/]")
        sys.exit(1)
    n_val = min(n - args.seq_len - 1, max(args.seq_len + 1, int(n * args.val_ratio)))
    n_train = n - n_val
    train_draws = draws[:n_train]
    val_draws = draws[n_train:]
    val_prizes = draws_with_prizes[n_train:] if draws_with_prizes else []

    train_ds = DrawSequenceDataset(train_draws, args.seq_len)
    val_ds = DrawSequenceDataset(val_draws, args.seq_len)
    train_loader = torch.utils.data.DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=(device.type == "cuda"),
    )
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model = NextDrawTransformer(
        seq_len=args.seq_len,
        d_model=args.d_model,
        nhead=args.nhead,
        num_encoder_layers=args.layers,
        dim_feedforward=args.dim_ff,
        dropout=args.dropout,
    ).to(device)
    criterion = torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_val_loss = float("inf")
    checkpoint_path = args.checkpoint or DEFAULT_CHECKPOINT_DIR / "transformer_4d.pt"

    for epoch in range(args.epochs):
        model.train()
        train_loss = 0.0
        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{args.epochs}", leave=True, disable=not verbose)
        for X, y in pbar:
            X, y = X.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(X)
            loss = criterion(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()
            pbar.set_postfix(loss=f"{loss.item():.4f}")
        scheduler.step()
        train_loss /= len(train_loader)

        model.eval()
        val_loss = 0.0
        if len(val_loader) > 0:
            with torch.no_grad():
                for X, y in val_loader:
                    X, y = X.to(device), y.to(device)
                    logits = model(X)
                    val_loss += criterion(logits, y).item()
            val_loss /= len(val_loader)
        else:
            val_loss = train_loss
        if len(val_loader) > 0 and val_loss < best_val_loss:
            best_val_loss = val_loss
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"model": model.state_dict(), "epoch": epoch + 1, "val_loss": val_loss}, checkpoint_path)
            if verbose:
                logger.info("Best checkpoint saved to {}", checkpoint_path)
        if verbose:
            logger.info("Epoch {}  train_loss={:.4f}  val_loss={:.4f}", epoch + 1, train_loss, val_loss if len(val_loader) > 0 else train_loss)

    # Eval: hit rate and P&L on validation set
    model.eval()
    all_preds: list[list[int]] = []
    if len(val_ds) == 0:
        console.print("[yellow]No validation samples (val set too small).[/]")
    else:
        with torch.no_grad():
            for X, _ in val_loader:
                X = X.to(device)
                preds = predict_top_k(model, X, k=23)
                all_preds.extend(preds)
        all_preds = all_preds[: len(val_ds)]
    seq_len = args.seq_len
    hits = 0
    for i, pred_indices in enumerate(all_preds or []):
        # Prediction i targets the next draw at val_draws[seq_len + i]
        actual = val_draws[seq_len + i][2]
        pred_set = {f"{idx:04d}" for idx in pred_indices}
        actual_norm = {str(n).strip().zfill(4) for n in actual}
        if pred_set & actual_norm:
            hits += 1
    hit_rate = hits / len(all_preds) if all_preds else 0
    results = [type("R", (), {"action": p})() for p in (all_preds or [])]
    prize_slice = [val_prizes[seq_len + i] for i in range(len(all_preds or [])) if seq_len + i < len(val_prizes)]
    while len(prize_slice) < len(results):
        prize_slice.append({})
    _cost, _win, _profit = compute_profit_loss(results, prize_slice, bet_per_number=1.0) if results else (0.0, 0.0, 0.0)

    summary = Table(title="Validation", box=None, show_header=False, padding=(0, 2))
    summary.add_column(style="dim")
    summary.add_column(style="bold")
    summary.add_row("Samples", str(len(all_preds or [])))
    summary.add_row("Hits", f"{hits}/{len(all_preds or [])}")
    summary.add_row("Hit rate", f"{hit_rate:.4f}")
    summary.add_row("Cost (RM)", f"{_cost:,.0f}")
    summary.add_row("Winnings (RM)", f"{_win:,.0f}")
    summary.add_row("Profit / Loss (RM)", f"[{'green' if _profit >= 0 else 'red'}]{_profit:+,.0f}[/]")
    console.print(Panel(summary, title="[bold green]Done[/]", border_style="green"))
    console.print(f"Checkpoint: {checkpoint_path}")


if __name__ == "__main__":
    main()
