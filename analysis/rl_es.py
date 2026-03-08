"""
Evolution Strategies (ES) for the 4D policy: gradient-free optimization.
Perturb policy parameters with Gaussian noise, evaluate fitness (total reward over backtest),
update the mean parameter vector by reward-weighted average of perturbations.
"""

from __future__ import annotations

import random
from pathlib import Path

import torch
from loguru import logger
from tqdm import tqdm

from analysis.load import get_draws_as_sets, get_draws_with_prizes, load_history
from analysis.prizes import compute_profit_loss
from analysis.rl import (
    DEFAULT_HIDDEN_SIZES,
    DEFAULT_K,
    PolicyNetwork,
    PolicyWithSequence,
    StepResult,
    backtest_episode,
    get_best_device,
    load_checkpoint,
    save_checkpoint,
)
from analysis.rl import DrawSequenceEncoder

DEFAULT_CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "output"


def get_flat_params(policy: PolicyNetwork | PolicyWithSequence) -> torch.Tensor:
    """Return a 1D copy of all policy parameters."""
    return torch.cat([p.data.view(-1).clone() for p in policy.parameters()])


def set_flat_params(policy: PolicyNetwork | PolicyWithSequence, flat: torch.Tensor) -> None:
    """In-place: set all policy parameters from a 1D vector."""
    offset = 0
    for p in policy.parameters():
        numel = p.numel()
        p.data.copy_(flat[offset : offset + numel].view_as(p))
        offset += numel


def run_es_backtest(
    csv_path: str | Path | None = None,
    draws: list[tuple[str, str, set[str]]] | None = None,
    draws_with_prizes: list[dict] | None = None,
    generations: int = 30,
    n_workers: int = 8,
    sigma: float = 0.02,
    lr: float = 0.01,
    k: int = DEFAULT_K,
    device: str | torch.device | None = None,
    max_draws: int | None = None,
    random_draws_seed: int | None = None,
    reward_mode: str = "prize",
    recency_decay: float = 0.0,
    seq_len: int = 0,
    seq_dim: int = 128,
    hidden_sizes: tuple[int, ...] = DEFAULT_HIDDEN_SIZES,
    prize_weighted_state: bool = False,
    checkpoint_path: str | Path | None = None,
    resume_from: str | Path | None = None,
    save_after_each_gen: bool = True,
    verbose: bool = True,
    seed: int | None = None,
    elitist: bool = False,
    resample_draws_each_gen: bool = False,
) -> tuple[list[StepResult], PolicyNetwork | PolicyWithSequence]:
    """
    Train the policy with Evolution Strategies: at each generation, sample n_workers
    perturbed parameter vectors (theta + sigma * noise), evaluate each with one
    backtest (total reward = fitness), then update theta using the reward-weighted
    average of the noise vectors (gradient-free estimate).

    If elitist=True: after the update, evaluate the new mean; if the best worker's
    reward was higher than the mean's reward, replace the policy with that best
    worker's parameters for the next generation.

    If resample_draws_each_gen=True: each generation uses a new random subset of
    max_draws from the full dataset (requires max_draws). Reduces overfitting to
    one fixed subset; fitness is noisier but policy generalizes better.

    Returns (results from final eval over draws, trained policy).
    """
    if draws is None:
        if csv_path is None:
            raise ValueError("Either csv_path or draws must be provided")
        df = load_history(str(csv_path))
        draws = get_draws_as_sets(df)
        if draws_with_prizes is None and reward_mode == "prize":
            draws_with_prizes = get_draws_with_prizes(df)

    full_draws: list[tuple[str, str, set[str]]] | None = None
    full_draws_prizes: list[dict] | None = None
    n_full = len(draws)

    if resample_draws_each_gen:
        if max_draws is None or max_draws > n_full:
            raise ValueError("resample_draws_each_gen requires max_draws <= len(draws)")
        full_draws = draws
        full_draws_prizes = draws_with_prizes
        if verbose:
            logger.info("Resampling {} draws each generation (anti-overfit)", max_draws)
    elif max_draws is not None and max_draws < len(draws):
        if random_draws_seed is not None:
            rng = torch.Generator().manual_seed(random_draws_seed)
            perm = torch.randperm(len(draws), generator=rng).tolist()[:max_draws]
            draws = [draws[i] for i in perm]
            if draws_with_prizes is not None:
                draws_with_prizes = [draws_with_prizes[i] for i in perm]
            if verbose:
                logger.info("Using {} random draws (max_draws, seed={})", len(draws), random_draws_seed)
        else:
            draws = draws[:max_draws]
            if draws_with_prizes is not None:
                draws_with_prizes = draws_with_prizes[:max_draws]
            if verbose:
                logger.info("Using first {} draws", len(draws))
    n = len(draws)
    if draws_with_prizes is not None:
        draws_with_prizes = draws_with_prizes[:n]
    if reward_mode == "prize" and (draws_with_prizes is None or len(draws_with_prizes) < n):
        raise ValueError("reward_mode='prize' requires draws_with_prizes (length >= draws)")
    if prize_weighted_state and (draws_with_prizes is None or len(draws_with_prizes) < n):
        raise ValueError("prize_weighted_state=True requires draws_with_prizes")

    if device is None:
        dev = get_best_device()
    else:
        dev = torch.device(device)

    if seq_len > 0:
        encoder = DrawSequenceEncoder(seq_len=seq_len, d_model=seq_dim).to(dev)
        policy = PolicyWithSequence(sequence_encoder=encoder, hidden_sizes=hidden_sizes).to(dev)
        if verbose:
            logger.info("ES with attention over last {} draws (seq_dim={})", seq_len, seq_dim)
    else:
        policy = PolicyNetwork(hidden_sizes=hidden_sizes).to(dev)

    start_gen = 0
    if resume_from is not None:
        try:
            load_checkpoint(resume_from, policy, optimizer=None, device=dev)
            if verbose:
                logger.info("Resumed from {}", resume_from)
        except (RuntimeError, FileNotFoundError) as e:
            if "state_dict" in str(e) or "Missing key" in str(e) or "Unexpected key" in str(e):
                if verbose:
                    logger.warning(
                        "Checkpoint architecture does not match (e.g. saved without --seq-len but running with --seq-len). Starting from scratch. Error: {}",
                        e,
                    )
            else:
                raise

    if seed is not None:
        torch.manual_seed(seed)

    flat = get_flat_params(policy)
    dim = flat.numel()
    if verbose:
        logger.info("ES: generations={}  workers={}  sigma={}  lr={}  param_dim={}", generations, n_workers, sigma, lr, dim)

    gen_range = range(start_gen, generations)
    gen_iterator = tqdm(gen_range, desc="ES", unit="gen", disable=not verbose, dynamic_ncols=True)

    for gen in gen_iterator:
        if resample_draws_each_gen and full_draws is not None:
            gen_seed = random.randint(0, 2**31 - 1)
            rng = torch.Generator(device=dev).manual_seed(gen_seed)
            perm = torch.randperm(n_full, generator=rng, device=dev).tolist()[:max_draws]
            draws = [full_draws[i] for i in perm]
            draws_with_prizes = [full_draws_prizes[i] for i in perm] if full_draws_prizes else None
            n = len(draws)

        noises = []
        rewards_list = []
        worker_iterator = tqdm(
            range(n_workers),
            desc=f"Gen {gen + 1}",
            unit="worker",
            leave=False,
            disable=not verbose,
            dynamic_ncols=True,
        )
        for w in worker_iterator:
            noise = torch.randn_like(flat, device=dev, dtype=flat.dtype)
            perturbed = (flat + sigma * noise).clone()
            set_flat_params(policy, perturbed)
            _, total_reward = backtest_episode(
                draws,
                policy,
                k=k,
                train=False,
                device=dev,
                verbose=False,
                log_every=999_999,
                epoch_label=f"W{w+1} ",
                reward_mode=reward_mode,
                recency_decay=recency_decay,
                seq_len=seq_len,
                draws_with_prizes=draws_with_prizes,
                prize_weighted_state=prize_weighted_state,
                show_progress_bar=verbose,
            )
            rewards_list.append(total_reward)
            noises.append(noise)
            if verbose:
                worker_iterator.set_postfix(reward=f"{total_reward:+.0f}")

        # Restore mean
        set_flat_params(policy, flat)

        # Normalize rewards (baseline subtraction + scale)
        rewards_t = torch.tensor(rewards_list, dtype=flat.dtype, device=dev)
        mean_r = rewards_t.mean().item()
        std_r = rewards_t.std().item()
        if std_r < 1e-8:
            std_r = 1.0
        normalized = (rewards_t - rewards_t.mean()) / std_r

        best_idx = int(rewards_t.argmax().item())
        best_r = rewards_list[best_idx]
        flat_before_update = flat.clone()

        # ES update: theta = theta + lr * (1/(n*sigma)) * sum_i (R_i - mean) * noise_i
        update = torch.zeros_like(flat, device=dev)
        for i in range(n_workers):
            update.add_(noises[i], alpha=normalized[i].item())
        flat = (flat + (lr / (n_workers * sigma)) * update).clone()
        set_flat_params(policy, flat)

        # Elitist: if best worker beat the updated mean, use best worker's params for next gen
        if elitist:
            _, mean_reward_after = backtest_episode(
                draws,
                policy,
                k=k,
                train=False,
                device=dev,
                verbose=False,
                log_every=999_999,
                reward_mode=reward_mode,
                recency_decay=recency_decay,
                seq_len=seq_len,
                draws_with_prizes=draws_with_prizes,
                prize_weighted_state=prize_weighted_state,
                show_progress_bar=False,
            )
            if best_r > mean_reward_after:
                flat = (flat_before_update + sigma * noises[best_idx]).clone()
                set_flat_params(policy, flat)
                if verbose:
                    logger.info("Elitist: kept best worker (reward {:.0f} > mean {:.0f})", best_r, mean_reward_after)
        if verbose:
            gen_iterator.set_postfix(mean_reward=f"{mean_r:.0f}", best=f"{best_r:.0f}")
            logger.info(
                "Gen {}: mean_reward={:.0f}  std_reward={:.0f}  best_reward={:.0f}",
                gen + 1,
                mean_r,
                std_r,
                best_r,
            )
        if checkpoint_path is not None and save_after_each_gen:
            save_checkpoint(policy, checkpoint_path, epoch=gen + 1, optimizer=None)
            if verbose and (gen + 1) % 5 == 0:
                logger.info("Checkpoint saved to {}", checkpoint_path)

    # Final eval with current (mean) policy
    if resample_draws_each_gen and full_draws is not None:
        rng = torch.Generator(device=dev).manual_seed(random.randint(0, 2**31 - 1))
        perm = torch.randperm(n_full, generator=rng, device=dev).tolist()[:max_draws]
        draws = [full_draws[i] for i in perm]
        draws_with_prizes = [full_draws_prizes[i] for i in perm] if full_draws_prizes else None
        if verbose:
            logger.info("Final eval on fresh random {} draws", len(draws))
    results, total = backtest_episode(
        draws,
        policy,
        k=k,
        train=False,
        device=dev,
        verbose=verbose,
        log_every=500,
        epoch_label="ES final ",
        reward_mode=reward_mode,
        recency_decay=recency_decay,
        seq_len=seq_len,
        draws_with_prizes=draws_with_prizes,
        prize_weighted_state=prize_weighted_state,
    )
    return results, policy
