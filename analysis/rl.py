"""
Reinforcement learning backtest: reward when at least one predicted number
matches the draw, punish when none match. Trains over full history.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import torch
import torch.nn as nn
from loguru import logger
from tqdm import tqdm

from analysis.load import get_draws_as_sets, load_history
from analysis.prizes import (
    COST_PER_DRAW_RM,
    MAGNUM_PRIZE_1ST,
    MAGNUM_PRIZE_2ND,
    MAGNUM_PRIZE_3RD,
    MAGNUM_PRIZE_CONSOLATION,
    MAGNUM_PRIZE_SPECIAL,
    compute_draw_winnings,
)

DEFAULT_CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "output"

N_NUMBERS = 10_000

# Default architecture: 3 hidden layers (512, 256, 256). See docs/RL_ARCHITECTURE.md.
DEFAULT_HIDDEN_SIZES = (512, 256, 256)


def get_best_device() -> torch.device:
    """Prefer CUDA, then Apple Silicon MPS, then CPU."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


DEFAULT_K = 23  # number of picks per step
REWARD_HIT = 1.0
REWARD_MISS = -1.0


def _number_to_idx(s: str) -> int:
    """4D string (e.g. '0123') -> index 0-9999."""
    s = str(s).strip().zfill(4)
    return int(s) if s.isdigit() else 0


def _idx_to_number(i: int) -> str:
    return f"{i:04d}"


def build_state_from_history(draws: list[tuple[str, str, set[str]]], end: int) -> torch.Tensor:
    """
    State = empirical frequency (counts) of each number in draws[0:end], normalized.
    Shape (10000,). If end==0, return uniform.
    """
    counts = torch.zeros(N_NUMBERS, dtype=torch.float32)
    if end <= 0:
        counts += 1.0 / N_NUMBERS
        return counts
    for t in range(end):
        for num in draws[t][2]:
            idx = _number_to_idx(num)
            if 0 <= idx < N_NUMBERS:
                counts[idx] += 1.0
    total = counts.sum()
    if total <= 0:
        counts += 1.0 / N_NUMBERS
    else:
        counts = counts / total
    return counts


def _add_draw_to_counts(counts: torch.Tensor, draw_numbers: set[str]) -> None:
    """In-place: add one draw's numbers to counts (for incremental state)."""
    for num in draw_numbers:
        idx = _number_to_idx(num)
        if 0 <= idx < N_NUMBERS:
            counts[idx] += 1.0


def _add_draw_to_counts_prize_weighted(counts: torch.Tensor, draw_prizes: dict) -> None:
    """In-place: add one draw's numbers to counts weighted by prize (1st=2500, 2nd=1000, …)."""
    first = draw_prizes.get("1st")
    second = draw_prizes.get("2nd")
    third = draw_prizes.get("3rd")
    special = set(draw_prizes.get("special") or [])
    consolation = set(draw_prizes.get("consolation") or [])
    if first:
        idx = _number_to_idx(str(first).strip())
        if 0 <= idx < N_NUMBERS:
            counts[idx] += float(MAGNUM_PRIZE_1ST)
    if second:
        idx = _number_to_idx(str(second).strip())
        if 0 <= idx < N_NUMBERS:
            counts[idx] += float(MAGNUM_PRIZE_2ND)
    if third:
        idx = _number_to_idx(str(third).strip())
        if 0 <= idx < N_NUMBERS:
            counts[idx] += float(MAGNUM_PRIZE_3RD)
    for num in special:
        idx = _number_to_idx(str(num).strip())
        if 0 <= idx < N_NUMBERS:
            counts[idx] += float(MAGNUM_PRIZE_SPECIAL)
    for num in consolation:
        idx = _number_to_idx(str(num).strip())
        if 0 <= idx < N_NUMBERS:
            counts[idx] += float(MAGNUM_PRIZE_CONSOLATION)


def draw_to_multi_hot(draw_numbers: set[str], device: torch.device | None = None) -> torch.Tensor:
    """One draw as multi-hot vector (10000,). 1.0 where a number appeared."""
    out = torch.zeros(N_NUMBERS, dtype=torch.float32, device=device)
    for num in draw_numbers:
        idx = _number_to_idx(num)
        if 0 <= idx < N_NUMBERS:
            out[idx] = 1.0
    return out


class DrawSequenceEncoder(nn.Module):
    """
    Time-series encoder over the last L draws. Each draw is multi-hot (10000,);
    we project to d_model, add positional encoding, then multi-head self-attention
    and mean-pool over time so the policy is aware of *which* numbers appeared *when*.
    """

    def __init__(
        self,
        seq_len: int = 32,
        d_model: int = 128,
        n_heads: int = 4,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.seq_len = seq_len
        self.d_model = d_model
        self.proj = nn.Linear(N_NUMBERS, d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, seq_len, d_model) * 0.02)
        self.attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=n_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, seq: torch.Tensor) -> torch.Tensor:
        """
        seq: (batch, seq_len, 10000) — batch of sequences of L draws (multi-hot).
        Returns: (batch, d_model) — context vector per batch item.
        """
        B, L, _ = seq.shape
        x = self.proj(seq)
        x = x + self.pos_embed[:, :L]
        x = self.dropout(x)
        # Self-attention: (B, L, d_model) -> need (L, B, d_model) for nn.MultiheadAttention
        attn_out, _ = self.attn(x, x, x, need_weights=False)
        x = self.norm(x + attn_out)
        return x.mean(dim=1)


class PolicyWithSequence(nn.Module):
    """
    Wrapper: when sequence_encoder is not None, state = concat(frequency, attention(sequence));
    otherwise state = frequency only. Policy always receives a single state vector.
    """

    def __init__(
        self,
        sequence_encoder: DrawSequenceEncoder | None = None,
        hidden_sizes: tuple[int, ...] = DEFAULT_HIDDEN_SIZES,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.sequence_encoder = sequence_encoder
        d_enc = sequence_encoder.d_model if sequence_encoder is not None else 0
        state_dim = N_NUMBERS + d_enc
        self.policy = PolicyNetwork(state_dim=state_dim, hidden_sizes=hidden_sizes, dropout=dropout)

    def forward(
        self,
        state_freq: torch.Tensor,
        state_seq: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if self.sequence_encoder is None or state_seq is None:
            return self.policy(state_freq)
        context = self.sequence_encoder(state_seq)
        full_state = torch.cat([state_freq, context], dim=-1)
        return self.policy(full_state)


@dataclass
class StepResult:
    state: torch.Tensor
    action: list[int]  # K indices
    reward: float
    hit: bool


class PolicyNetwork(nn.Module):
    """
    Maps state (state_dim) -> logits (10000). We sample K indices from softmax(logits).
    hidden_sizes: tuple of widths for each hidden layer, e.g. (512, 256, 256).
    """

    def __init__(
        self,
        state_dim: int = N_NUMBERS,
        hidden_sizes: tuple[int, ...] = DEFAULT_HIDDEN_SIZES,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if not hidden_sizes:
            raise ValueError("hidden_sizes must be non-empty")
        layers: list[nn.Module] = []
        dims = [state_dim, *hidden_sizes, N_NUMBERS]
        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i + 1]))
            if i < len(dims) - 2:
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(dropout))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def sample_action(logits: torch.Tensor, k: int = DEFAULT_K) -> tuple[list[int], torch.Tensor, torch.Tensor]:
    """
    Sample k indices without replacement. Returns (indices, log_prob, probs).
    probs used for entropy bonus in training.
    If logits produce non-finite or invalid probs, fall back to uniform to avoid multinomial crash.
    """
    logits = logits.clamp(min=-50.0, max=50.0)
    probs = torch.softmax(logits, dim=-1)
    if not torch.isfinite(probs).all() or (probs < 0).any():
        probs = torch.ones_like(probs, dtype=probs.dtype, device=probs.device) / probs.size(-1)
    probs = probs.clamp(min=1e-8)
    probs = probs / probs.sum(dim=-1, keepdim=True)
    indices = torch.multinomial(probs, num_samples=k, replacement=False)
    log_probs = torch.log(probs[indices] + 1e-8)
    log_prob = log_probs.sum()
    return indices.tolist(), log_prob, probs


def policy_entropy(probs: torch.Tensor) -> torch.Tensor:
    """Entropy H = -sum p log p over the full distribution (for exploration bonus)."""
    return -(probs * (probs + 1e-8).log()).sum()


def compute_reward(
    predicted_indices: list[int],
    actual_numbers: set[str],
    reward_mode: str = "binary",
) -> tuple[float, bool]:
    """
    reward_mode "binary": +1 if any hit, else -1 (sparse).
    reward_mode "count": reward = number of hits (0..K), denser signal for learning.
    """
    pred_set = {_idx_to_number(i) for i in predicted_indices}
    actual_normalized = {str(n).strip().zfill(4) for n in actual_numbers if str(n).strip()}
    n_hits = len(pred_set & actual_normalized)
    hit = n_hits > 0
    if reward_mode == "count":
        # Denser reward: 0 to n_hits (max ~23). Scale to similar magnitude as binary for stability.
        return float(n_hits), hit
    return REWARD_HIT if hit else REWARD_MISS, hit


def backtest_episode(
    draws: list[tuple[str, str, set[str]]],
    policy: PolicyNetwork | PolicyWithSequence,
    k: int = DEFAULT_K,
    train: bool = True,
    device: torch.device | None = None,
    verbose: bool = True,
    log_every: int = 500,
    epoch_label: str = "",
    reward_mode: str = "binary",
    baseline_ema: float = 0.99,
    entropy_coef: float = 0.01,
    recency_decay: float = 0.0,
    seq_len: int = 0,
    draws_with_prizes: list[dict] | None = None,
    prize_weighted_state: bool = False,
    on_step_callback: Callable[[int, int, float, float, float, str], None] | None = None,
    show_progress_bar: bool = True,
) -> tuple[list[StepResult], float]:
    """
    One pass over full history. If train=True: REINFORCE with baseline and entropy bonus.
    reward_mode "prize": reward = (winnings - 23) RM using Magnum prizes; requires draws_with_prizes.
    seq_len > 0: use attention over last seq_len draws (policy must be PolicyWithSequence).
    """
    if device is None:
        device = next(policy.parameters()).device
    policy.train(train)
    optimizer = getattr(policy, "_optimizer", None)
    if train and optimizer is None:
        optimizer = torch.optim.Adam(policy.parameters(), lr=1e-3)
        policy._optimizer = optimizer

    n = len(draws)
    results: list[StepResult] = []
    total_reward = 0.0
    hits_so_far = 0

    # Running baseline for variance reduction (REINFORCE with baseline)
    running_baseline = 0.0

    # Incremental state; recency_decay in (0,1) applies exponential decay so recent draws matter more
    counts = torch.zeros(N_NUMBERS, dtype=torch.float32)
    total_counts = 0.0
    uniform = torch.ones(N_NUMBERS, dtype=torch.float32) / N_NUMBERS

    # Sequence of last L draws (multi-hot) for attention over time when seq_len > 0
    seq_deque: deque[torch.Tensor] = deque(maxlen=seq_len) if seq_len > 0 else deque()

    mode = "train" if train else "eval"
    use_tqdm = verbose and show_progress_bar and (on_step_callback is None)
    iterator = tqdm(
        range(n),
        desc=f"{epoch_label}{mode}".strip() or "step",
        unit="draw",
        leave=True,
        disable=not use_tqdm,
        dynamic_ncols=True,
    ) if use_tqdm else range(n)

    loss_val = 0.0
    for t in iterator:
        if recency_decay > 0:
            total = counts.sum()
            state = (counts / total).to(device) if total > 0 else uniform.to(device)
        else:
            state = uniform.to(device) if total_counts <= 0 else (counts / total_counts).to(device)
        _, actual_set = draws[t][1], draws[t][2]

        with torch.set_grad_enabled(train):
            if seq_len > 0 and len(seq_deque) > 0:
                state_seq = torch.stack(list(seq_deque), dim=0)
                if state_seq.size(0) < seq_len:
                    pad = torch.zeros(seq_len - state_seq.size(0), N_NUMBERS, dtype=state_seq.dtype)
                    state_seq = torch.cat([pad, state_seq], dim=0)
                state_seq = state_seq.unsqueeze(0).to(device)
                state_freq = state.unsqueeze(0)
                logits = policy(state_freq, state_seq).squeeze(0)
            elif seq_len > 0:
                state_seq = torch.zeros(1, seq_len, N_NUMBERS, dtype=torch.float32, device=device)
                logits = policy(state.unsqueeze(0), state_seq).squeeze(0)
            else:
                logits = policy(state.unsqueeze(0)).squeeze(0)
            action_list, log_prob, probs = sample_action(logits, k=k)
            if reward_mode == "prize" and draws_with_prizes is not None and t < len(draws_with_prizes):
                winnings = compute_draw_winnings(action_list, draws_with_prizes[t])
                reward = winnings - COST_PER_DRAW_RM
                hit = winnings > 0
            else:
                reward, hit = compute_reward(action_list, actual_set, reward_mode=reward_mode)

        results.append(StepResult(state=state, action=action_list, reward=reward, hit=hit))
        total_reward += reward
        if hit:
            hits_so_far += 1

        if train and optimizer is not None:
            advantage = reward - running_baseline
            running_baseline = baseline_ema * running_baseline + (1.0 - baseline_ema) * reward

            entropy = policy_entropy(probs)
            loss = -log_prob * advantage - entropy_coef * entropy
            loss_val = loss.item()

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
            optimizer.step()

        if on_step_callback is not None:
            hit_rate = hits_so_far / (t + 1)
            on_step_callback(t + 1, n, reward, hit_rate, loss_val, epoch_label)

        if verbose and (t + 1) % max(1, log_every) == 0:
            rate = hits_so_far / (t + 1)
            iterator.set_postfix(reward=f"{total_reward:+.0f}", hits=hits_so_far, hit_rate=f"{rate:.4f}")

        if recency_decay > 0:
            counts.mul_(recency_decay)
        if prize_weighted_state and draws_with_prizes is not None and t < len(draws_with_prizes):
            _add_draw_to_counts_prize_weighted(counts, draws_with_prizes[t])
            total_counts += (
                (1 if draws_with_prizes[t].get("1st") else 0) * MAGNUM_PRIZE_1ST
                + (1 if draws_with_prizes[t].get("2nd") else 0) * MAGNUM_PRIZE_2ND
                + (1 if draws_with_prizes[t].get("3rd") else 0) * MAGNUM_PRIZE_3RD
                + len(set(draws_with_prizes[t].get("special") or [])) * MAGNUM_PRIZE_SPECIAL
                + len(set(draws_with_prizes[t].get("consolation") or [])) * MAGNUM_PRIZE_CONSOLATION
            )
        else:
            _add_draw_to_counts(counts, actual_set)
            total_counts += len(actual_set)
        if seq_len > 0:
            seq_deque.append(draw_to_multi_hot(actual_set))

    return results, total_reward


def save_checkpoint(
    policy: PolicyNetwork,
    path: str | Path,
    epoch: int = 0,
    optimizer: torch.optim.Optimizer | None = None,
) -> None:
    """Save policy state (and optionally optimizer, epoch) for resuming later. Uses atomic write (tmp then rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    state = {
        "policy_state_dict": policy.state_dict(),
        "epoch": epoch,
    }
    if optimizer is not None:
        state["optimizer_state_dict"] = optimizer.state_dict()
    torch.save(state, tmp)
    tmp.replace(path)


def load_checkpoint(
    path: str | Path,
    policy: PolicyNetwork,
    optimizer: torch.optim.Optimizer | None = None,
    device: torch.device | None = None,
    max_retries: int = 3,
) -> int:
    """
    Load policy (and optionally optimizer) from checkpoint.
    Returns the epoch that was saved (so you can resume from epoch+1).
    Retries on read errors (e.g. file still being written) for --forever mode.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {path}")
    last_err = None
    for attempt in range(max_retries):
        try:
            state = torch.load(path, map_location=device or "cpu", weights_only=True)
            policy.load_state_dict(state["policy_state_dict"])
            if optimizer is not None and "optimizer_state_dict" in state:
                optimizer.load_state_dict(state["optimizer_state_dict"])
            return int(state.get("epoch", 0))
        except RuntimeError as e:
            last_err = e
            if "zip" in str(e).lower() or "central directory" in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
            raise
    raise last_err


def run_rl_backtest(
    csv_path: str | None = None,
    draws: list[tuple[str, str, set[str]]] | None = None,
    epochs: int = 3,
    k: int = DEFAULT_K,
    lr: float = 1e-3,
    device: str | None = None,
    max_draws: int | None = None,
    verbose: bool = True,
    log_every: int = 500,
    checkpoint_path: str | Path | None = None,
    resume_from: str | Path | None = None,
    save_after_each_epoch: bool = True,
    reward_mode: str = "count",
    baseline_ema: float = 0.99,
    entropy_coef: float = 0.01,
    recency_decay: float = 0.0,
    seq_len: int = 0,
    seq_dim: int = 128,
    draws_with_prizes: list[dict] | None = None,
    prize_weighted_state: bool = False,
    hidden_sizes: tuple[int, ...] = DEFAULT_HIDDEN_SIZES,
    skip_final_eval: bool = False,
    random_draws_seed: int | None = None,
    on_step_callback: Callable[[int, int, float, float, float, str], None] | None = None,
) -> tuple[list[StepResult], PolicyNetwork | PolicyWithSequence]:
    """
    Load history (or use provided draws), train policy for multiple passes.
    When reward_mode == "prize", draws_with_prizes must be provided (same length/order as draws).
    When prize_weighted_state=True, state uses prize-weighted counts (1st=2500, 2nd=1000, …); requires draws_with_prizes.
    When skip_final_eval=True (e.g. --forever), only run training; no eval at end (caller runs eval on Ctrl+C).
    Returns (last epoch step results, trained policy).
    """
    if draws is None:
        if csv_path is None:
            raise ValueError("Either csv_path or draws must be provided")
        df = load_history(csv_path)
        draws = get_draws_as_sets(df)
    if max_draws is not None and max_draws < len(draws):
        if random_draws_seed is not None:
            rng = torch.Generator().manual_seed(random_draws_seed)
            perm = torch.randperm(len(draws), generator=rng).tolist()[:max_draws]
            draws = [draws[i] for i in perm]
            if draws_with_prizes is not None:
                draws_with_prizes = [draws_with_prizes[i] for i in perm]
            if verbose:
                logger.info("Using {} random draws (--max-draws, seed={})", len(draws), random_draws_seed)
        else:
            draws = draws[:max_draws]
            if draws_with_prizes is not None:
                draws_with_prizes = draws_with_prizes[:max_draws]
            if verbose:
                logger.info("Using first {} draws in dataset order (--max-draws; not random)", len(draws))
    n = len(draws)
    if draws_with_prizes is not None:
        draws_with_prizes = draws_with_prizes[:n]
    if reward_mode == "prize" and (draws_with_prizes is None or len(draws_with_prizes) < n):
        raise ValueError("reward_mode='prize' requires draws_with_prizes (length >= draws)")
    if prize_weighted_state and (draws_with_prizes is None or len(draws_with_prizes) < n):
        raise ValueError("prize_weighted_state=True requires draws_with_prizes (length >= draws)")
    if device is None:
        dev = get_best_device()
    else:
        dev = torch.device(device)
    if verbose:
        logger.info("Draws: {}  |  Device: {}  |  Steps per epoch: {}  |  Log every: {} steps", n, dev, n, log_every)

    if seq_len > 0:
        encoder = DrawSequenceEncoder(seq_len=seq_len, d_model=seq_dim).to(dev)
        policy = PolicyWithSequence(sequence_encoder=encoder, hidden_sizes=hidden_sizes).to(dev)
        if verbose:
            logger.info("Attention over last {} draws (seq_dim={})", seq_len, seq_dim)
    else:
        policy = PolicyNetwork(hidden_sizes=hidden_sizes).to(dev)
    optimizer = torch.optim.Adam(policy.parameters(), lr=lr)
    policy._optimizer = optimizer
    start_epoch = 0

    if resume_from is not None:
        saved_epoch = load_checkpoint(resume_from, policy, optimizer=optimizer, device=dev)
        start_epoch = saved_epoch
        # When resuming, run exactly one more training epoch (avoids epoch jump 48->53 in --forever)
        epochs = start_epoch + 1
        if verbose:
            logger.info("Resumed from {} (saved after epoch {}). Continuing from epoch {}.", resume_from, saved_epoch, saved_epoch + 1)

    for ep in range(start_epoch, epochs):
        if verbose:
            logger.info("Epoch {}/{}", ep + 1, epochs)
        results, total = backtest_episode(
            draws, policy, k=k, train=True, device=dev,
            verbose=verbose, log_every=log_every, epoch_label=f"E{ep+1} ",
            reward_mode=reward_mode, baseline_ema=baseline_ema, entropy_coef=entropy_coef,
            recency_decay=recency_decay, seq_len=seq_len, draws_with_prizes=draws_with_prizes,
            prize_weighted_state=prize_weighted_state,
            on_step_callback=on_step_callback,
            show_progress_bar=on_step_callback is None,
        )
        hits = sum(1 for r in results if r.hit)
        if verbose:
            logger.info("Epoch {} done: total_reward={:.0f}  hits={}/{}  hit_rate={:.4f}", ep + 1, total, hits, n, hits / n)
        if checkpoint_path is not None and save_after_each_epoch:
            save_checkpoint(policy, checkpoint_path, epoch=ep + 1, optimizer=optimizer)
            if verbose:
                logger.info("Checkpoint saved to {}", checkpoint_path)

    if checkpoint_path is not None:
        save_checkpoint(policy, checkpoint_path, epoch=epochs, optimizer=optimizer)
        if verbose:
            logger.info("Final checkpoint saved to {}", checkpoint_path)

    if skip_final_eval:
        return results, policy

    if verbose:
        logger.info("Final eval (no grad)")
    results, total = backtest_episode(
        draws, policy, k=k, train=False, device=dev,
        verbose=verbose, log_every=log_every, epoch_label="",
        reward_mode=reward_mode, recency_decay=recency_decay, seq_len=seq_len,
        draws_with_prizes=draws_with_prizes, prize_weighted_state=prize_weighted_state,
    )
    return results, policy


def run_final_eval(
    checkpoint_path: str | Path,
    draws: list[tuple[str, str, set[str]]],
    k: int = DEFAULT_K,
    device: torch.device | str | None = None,
    hidden_sizes: tuple[int, ...] = DEFAULT_HIDDEN_SIZES,
    seq_len: int = 0,
    seq_dim: int = 128,
    recency_decay: float = 0.0,
    draws_with_prizes: list[dict] | None = None,
    prize_weighted_state: bool = False,
) -> list[StepResult]:
    """
    Load policy from checkpoint and run one eval pass (no training).
    Used after Ctrl+C in --forever mode to show final summary.
    """
    path = Path(checkpoint_path)
    if not path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {path}")
    if device is None:
        dev = get_best_device()
    else:
        dev = torch.device(device)
    if seq_len > 0:
        encoder = DrawSequenceEncoder(seq_len=seq_len, d_model=seq_dim).to(dev)
        policy = PolicyWithSequence(sequence_encoder=encoder, hidden_sizes=hidden_sizes).to(dev)
    else:
        policy = PolicyNetwork(hidden_sizes=hidden_sizes).to(dev)
    load_checkpoint(path, policy, optimizer=None, device=dev)
    results, _ = backtest_episode(
        draws, policy, k=k, train=False, device=dev,
        verbose=False, log_every=999_999, epoch_label="",
        reward_mode="prize", recency_decay=recency_decay, seq_len=seq_len,
        draws_with_prizes=draws_with_prizes, prize_weighted_state=prize_weighted_state,
    )
    return results
