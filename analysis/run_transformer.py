#!/usr/bin/env python3
"""
Train a Transformer to predict the next 4D draw from a sequence of past draws.
Fast supervised training with BCE loss; eval hit rate and P&L.
"""

from __future__ import annotations

import argparse
import random
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
    DrawSequenceDataset,
    NextDrawTransformer,
    draw_set_to_multi_hot,
    predict_top_k,
)

DEFAULT_CHECKPOINT_DIR = _root / "output"


def _state_dict_for_load(
    state_dict: dict,
    model: torch.nn.Module | None = None,
) -> dict:
    """Strip torch.compile prefix and fix shape mismatches (e.g. pos_encoder.pe when seq_len differs)."""
    prefix = "_orig_mod."
    if any(k.startswith(prefix) for k in state_dict):
        state_dict = {k.removeprefix(prefix): v for k, v in state_dict.items()}
    if model is None:
        return state_dict
    # Fix pos_encoder.pe if checkpoint was saved with different seq_len
    pe_key = "pos_encoder.pe"
    if pe_key in state_dict:
        pe = state_dict[pe_key]
        model_pe = getattr(model, "pos_encoder", None) and getattr(model.pos_encoder, "pe", None)
        if model_pe is not None and pe.shape != model_pe.shape and pe.dim() == 3:
            # Slice or pad on sequence dim (dim=1) to match model
            need = model_pe.shape[1]
            if pe.shape[1] >= need:
                state_dict = {**state_dict, pe_key: pe[:, :need, :].clone()}
            else:
                # Checkpoint has shorter PE; copy and leave rest as model init (rare)
                new_pe = model_pe.clone()
                new_pe[:, : pe.shape[1], :] = pe
                state_dict = {**state_dict, pe_key: new_pe}
    return state_dict


def _transformer_kwargs(args: argparse.Namespace) -> dict:
    return {
        "seq_len": args.seq_len,
        "d_model": args.d_model,
        "nhead": args.nhead,
        "num_encoder_layers": args.layers,
        "dim_feedforward": args.dim_ff,
        "dropout": args.dropout,
        "n_kv_heads": getattr(args, "n_kv_heads", None),
        "use_rope": getattr(args, "rope", False),
        "drop_path": getattr(args, "drop_path", 0.0),
        "layer_scale": getattr(args, "layer_scale", 0.0),
        "use_grad_checkpoint": getattr(args, "grad_checkpoint", False),
    }


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
    parser.add_argument("--dropout", type=float, default=0.1, help="Dropout rate (default 0.1; try 0.15–0.2 to reduce overfitting)")
    parser.add_argument("--rope", action="store_true", help="Use RoPE instead of sinusoidal position encoding")
    parser.add_argument("--n-kv-heads", type=int, default=None, metavar="N", help="GQA: number of K/V heads (default = nhead; 2 for 8 heads is faster)")
    parser.add_argument("--drop-path", type=float, default=0.0, help="Stochastic depth rate (default 0; try 0.1)")
    parser.add_argument("--layer-scale", type=float, default=0.0, help="LayerScale init (default 0; try 0.1)")
    parser.add_argument("--grad-checkpoint", action="store_true", help="Gradient checkpointing (saves memory, slower backward)")
    parser.add_argument("--fast", action="store_true", help="Preset: --rope --n-kv-heads 2 --grad-checkpoint (faster, less memory)")
    parser.add_argument("--weight-decay", type=float, default=0.01, help="AdamW weight decay (default 0.01)")
    parser.add_argument("--epochs", type=int, default=20, help="Max training epochs (default 20; early stopping may stop sooner)")
    parser.add_argument("--early-stopping", type=int, default=5, metavar="N", help="Stop if val loss does not improve for N epochs (default 5; 0 = disabled)")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size (default 64)")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate / max LR (default 3e-4)")
    parser.add_argument("--scheduler", type=str, default="onecycle", choices=("cosine", "onecycle"), help="LR schedule: onecycle (warmup+decay, helps avoid plateaus) or cosine (default onecycle)")
    parser.add_argument("--label-smoothing", type=float, default=1e-4, help="Smooth BCE targets: negatives 0->this value (default 1e-4). 0 = no smoothing.")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Fraction of data for validation (default 0.1)")
    parser.add_argument("--max-draws", type=int, default=None, help="Cap total draws (for quick runs)")
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--checkpoint", type=Path, default=None, help="Save/load model path (default output/transformer_4d.pt)")
    parser.add_argument("--no-resume", action="store_true", help="Do not load checkpoint when training; start from scratch even if checkpoint exists")
    parser.add_argument("--backtest", action="store_true", help="Backtest only: load checkpoint and evaluate on N random draws (no training)")
    parser.add_argument("--backtest-draws", type=int, default=1000, help="Number of random draws to backtest on when --backtest (default 1000)")
    parser.add_argument("--amp", action="store_true", default=True, help="Use mixed precision (faster on GPU/MPS, default on)")
    parser.add_argument("--no-amp", action="store_false", dest="amp", help="Disable mixed precision")
    parser.add_argument("--compile", action="store_true", dest="use_compile", default=True, help="Use torch.compile(model) for speed (default on)")
    parser.add_argument("--no-compile", action="store_false", dest="use_compile", help="Disable torch.compile")
    parser.add_argument("--workers", type=int, default=None, help="DataLoader num_workers (default 4 on cuda/mps, 0 on cpu)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if getattr(args, "fast", False):
        args.rope = True
        if args.n_kv_heads is None and args.nhead >= 4:
            args.n_kv_heads = 2
        args.grad_checkpoint = True

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
    checkpoint_path = args.checkpoint or DEFAULT_CHECKPOINT_DIR / "transformer_4d.pt"

    df = load_history(str(csv_path))
    draws = get_draws_as_sets(df)
    draws_with_prizes = get_draws_with_prizes(df)
    if args.max_draws is not None and args.max_draws < len(draws):
        draws = draws[: args.max_draws]
        draws_with_prizes = draws_with_prizes[: len(draws)] if draws_with_prizes else []
    n = len(draws)

    if args.backtest:
        if not checkpoint_path.is_file():
            console.print(f"[red]Checkpoint not found:[/] {checkpoint_path}")
            sys.exit(1)
        valid_indices = list(range(args.seq_len, n))
        n_bt = min(args.backtest_draws, len(valid_indices))
        if n_bt <= 0:
            console.print("[red]Not enough draws for backtest (need seq_len + at least 1).[/]")
            sys.exit(1)
        sample_indices = random.sample(valid_indices, n_bt)
        console.print(Panel("[bold]4D Transformer backtest[/] — Evaluate on N random draws (no seed).", title="[bold cyan]Backtest[/]", border_style="cyan"))
        config_bt = Table(show_header=False, box=None, padding=(0, 2))
        config_bt.add_column(style="dim")
        config_bt.add_column()
        config_bt.add_row("Checkpoint", str(checkpoint_path))
        config_bt.add_row("Backtest draws", str(n_bt))
        config_bt.add_row("Seq len", str(args.seq_len))
        config_bt.add_row("Device", str(device))
        console.print(config_bt)
        console.print()
        model = NextDrawTransformer(**_transformer_kwargs(args)).to(device)
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=True)
        model.load_state_dict(_state_dict_for_load(ckpt["model"], model), strict=True)
        model.eval()
        all_preds: list[list[int]] = []
        batch_size = 64
        with torch.no_grad():
            for i in tqdm(range(0, n_bt, batch_size), desc="Backtest", disable=not verbose):
                batch_end = min(i + batch_size, n_bt)
                batch_indices = sample_indices[i:batch_end]
                X_list = []
                for t in batch_indices:
                    seq_draws = [draws[t - args.seq_len + k][2] for k in range(args.seq_len)]
                    X_list.append(torch.stack([draw_set_to_multi_hot(s) for s in seq_draws], dim=0))
                X = torch.stack(X_list, dim=0).to(device)
                preds = predict_top_k(model, X, k=23)
                all_preds.extend(preds)
        bt_prizes = [draws_with_prizes[t] if t < len(draws_with_prizes) else {} for t in sample_indices]
        while len(bt_prizes) < len(all_preds):
            bt_prizes.append({})
        hits = 0
        for idx, pred_indices in enumerate(all_preds):
            t = sample_indices[idx]
            actual = draws[t][2]
            pred_set = {f"{x:04d}" for x in pred_indices}
            actual_norm = {str(a).strip().zfill(4) for a in actual}
            if pred_set & actual_norm:
                hits += 1
        hit_rate = hits / len(all_preds) if all_preds else 0
        results = [type("R", (), {"action": p})() for p in all_preds]
        _cost, _win, _profit = compute_profit_loss(results, bt_prizes, bet_per_number=1.0)
        summary = Table(title="Backtest", box=None, show_header=False, padding=(0, 2))
        summary.add_column(style="dim")
        summary.add_column(style="bold")
        summary.add_row("Draws", str(len(all_preds)))
        summary.add_row("Hits", f"{hits}/{len(all_preds)}")
        summary.add_row("Hit rate", f"{hit_rate:.4f}")
        summary.add_row("Cost (RM)", f"{_cost:,.0f}")
        summary.add_row("Winnings (RM)", f"{_win:,.0f}")
        summary.add_row("Profit / Loss (RM)", f"[{'green' if _profit >= 0 else 'red'}]{_profit:+,.0f}[/]")
        console.print(Panel(summary, title="[bold green]Done[/]", border_style="green"))
        return

    console.print(Panel("[bold]4D Transformer[/] — Next-draw prediction from past sequence.", title="[bold cyan]Train[/]", border_style="cyan"))
    num_workers = args.workers if args.workers is not None else (4 if device.type in ("cuda", "mps") else 0)
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
    config.add_row("Weight decay", str(args.weight_decay))
    config.add_row("Scheduler", args.scheduler)
    if getattr(args, "early_stopping", 0) > 0:
        config.add_row("Early stopping", f"patience={args.early_stopping}")
    if getattr(args, "rope", False):
        config.add_row("RoPE", "on")
    if getattr(args, "n_kv_heads", None) is not None:
        config.add_row("GQA n_kv_heads", str(args.n_kv_heads))
    if getattr(args, "drop_path", 0) > 0:
        config.add_row("Drop path", str(args.drop_path))
    if getattr(args, "layer_scale", 0) > 0:
        config.add_row("Layer scale", str(args.layer_scale))
    if getattr(args, "grad_checkpoint", False):
        config.add_row("Grad checkpoint", "on")
    if getattr(args, "fast", False):
        config.add_row("Preset", "fast (rope + GQA + grad checkpoint)")
    config.add_row("Workers", str(num_workers))
    if args.amp:
        config.add_row("AMP", "on (mixed precision)")
    if getattr(args, "use_compile", False):
        config.add_row("Compile", "on")
    if args.label_smoothing > 0:
        config.add_row("Label smoothing", str(args.label_smoothing))
    console.print(config)
    console.print()

    # draws, draws_with_prizes, n already set above (before backtest branch)
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
        num_workers=num_workers,
        pin_memory=(device.type == "cuda"),
    )
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=num_workers)

    model = NextDrawTransformer(**_transformer_kwargs(args)).to(device)
    start_epoch = 0
    best_val_loss = float("inf")
    if checkpoint_path.is_file() and not getattr(args, "no_resume", False):
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=True)
        try:
            model.load_state_dict(_state_dict_for_load(ckpt["model"], model), strict=True)
            start_epoch = ckpt.get("epoch", 0)
            best_val_loss = ckpt.get("val_loss", float("inf"))
            if verbose:
                logger.info("Resumed from {} (saved epoch {}, val_loss={:.4f})", checkpoint_path, start_epoch, best_val_loss)
        except Exception as e:
            if verbose:
                logger.warning("Could not resume from {}: {} — starting from scratch", checkpoint_path, e)
    if getattr(args, "use_compile", False) and hasattr(torch, "compile"):
        model = torch.compile(model, mode="reduce-overhead")
    criterion = torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    use_amp = args.amp and device.type in ("cuda", "mps")
    scaler = torch.amp.GradScaler("cuda") if use_amp and device.type == "cuda" else None
    total_steps = args.epochs * len(train_loader)
    if args.scheduler == "onecycle":
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=args.lr,
            total_steps=total_steps,
            pct_start=0.1,
            anneal_strategy="cos",
        )
    else:
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    step = 0
    early_stopping_patience = getattr(args, "early_stopping", 0)
    epochs_without_improvement = 0

    for epoch in range(args.epochs):
        model.train()
        train_loss = 0.0
        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{args.epochs}", leave=True, disable=not verbose)
        for X, y in pbar:
            X, y = X.to(device, non_blocking=True), y.to(device, non_blocking=True)
            if args.label_smoothing > 0:
                y = y * (1.0 - args.label_smoothing) + args.label_smoothing * (1.0 - y).clamp(0, 1)
            optimizer.zero_grad()
            if use_amp:
                with torch.amp.autocast(device.type):
                    logits = model(X)
                    loss = criterion(logits, y)
                if scaler is not None:
                    scaler.scale(loss).backward()
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
            else:
                logits = model(X)
                loss = criterion(logits, y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            if args.scheduler == "onecycle":
                scheduler.step()
            step += 1
            train_loss += loss.item()
            pbar.set_postfix(loss=f"{loss.item():.4f}", lr=f"{scheduler.get_last_lr()[0]:.2e}")
        if args.scheduler == "cosine":
            scheduler.step()
        train_loss /= len(train_loader)

        model.eval()
        val_loss = 0.0
        if len(val_loader) > 0:
            with torch.no_grad():
                for X, y in val_loader:
                    X, y = X.to(device), y.to(device)
                    if use_amp:
                        with torch.amp.autocast(device.type):
                            logits = model(X)
                            val_loss += criterion(logits, y).item()
                    else:
                        logits = model(X)
                        val_loss += criterion(logits, y).item()
            val_loss /= len(val_loader)
        else:
            val_loss = train_loss
        if len(val_loader) > 0 and val_loss < best_val_loss:
            best_val_loss = val_loss
            epochs_without_improvement = 0
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"model": model.state_dict(), "epoch": epoch + 1, "val_loss": val_loss}, checkpoint_path)
            if verbose:
                logger.info("Best checkpoint saved to {}", checkpoint_path)
        else:
            if len(val_loader) > 0:
                epochs_without_improvement += 1
        if verbose:
            logger.info("Epoch {}  train_loss={:.4f}  val_loss={:.4f}", epoch + 1, train_loss, val_loss if len(val_loader) > 0 else train_loss)
        if early_stopping_patience > 0 and len(val_loader) > 0 and epochs_without_improvement >= early_stopping_patience:
            if verbose:
                logger.info("Early stopping (val loss did not improve for {} epochs). Best val_loss={:.4f}", early_stopping_patience, best_val_loss)
            break

    # Load best checkpoint so final eval uses best model, not last epoch
    if checkpoint_path.is_file() and len(val_loader) > 0:
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=True)
        state = _state_dict_for_load(ckpt["model"], model)
        # Compiled model expects _orig_mod.* keys; checkpoint may have raw keys
        first_key = next(iter(model.state_dict()), "")
        if first_key.startswith("_orig_mod.") and not next(iter(state), "").startswith("_orig_mod."):
            state = {"_orig_mod." + k: v for k, v in state.items()}
        model.load_state_dict(state, strict=True)
        if verbose:
            logger.info("Loaded best checkpoint (epoch {}, val_loss={:.4f}) for final eval", ckpt.get("epoch", "?"), ckpt.get("val_loss", float("nan")))

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
