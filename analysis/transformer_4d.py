"""
Transformer model for 4D next-draw prediction.
Input: sequence of past draws (each draw = multi-hot over 10k numbers).
Output: logits over 10k numbers; top-23 taken as prediction.
Trained with BCE on multi-hot target of the next draw.
"""

from __future__ import annotations

import math
import torch
import torch.nn as nn

N_NUMBERS = 10_000


def _number_to_idx(s: str) -> int:
    s = str(s).strip().zfill(4)
    return int(s) if s.isdigit() else 0


def draw_set_to_multi_hot(draw_numbers: set[str], device: torch.device | None = None) -> torch.Tensor:
    """One draw as multi-hot (10000,). 1.0 where a number appeared."""
    out = torch.zeros(N_NUMBERS, dtype=torch.float32, device=device)
    for num in draw_numbers:
        idx = _number_to_idx(num)
        if 0 <= idx < N_NUMBERS:
            out[idx] = 1.0
    return out


def idx_to_number(i: int) -> str:
    return f"{i:04d}"


class DrawSequenceDataset(torch.utils.data.Dataset):
    """
    Dataset of (sequence of draws, next draw).
    Each sample: X (seq_len, 10000) multi-hot sequence, y (10000) multi-hot next draw.
    """

    def __init__(
        self,
        draws: list[tuple[str, str, set[str]]],
        seq_len: int,
    ) -> None:
        self.draws = draws
        self.seq_len = seq_len
        # Valid start indices: we need draws[t-seq_len:t] and draws[t], so t in [seq_len, len(draws)-1]
        self.valid_starts = list(range(seq_len, len(draws)))

    def __len__(self) -> int:
        return len(self.valid_starts)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        t = self.valid_starts[idx]
        # X: draws[t-seq_len : t] as (seq_len, 10000)
        seq_draws = [self.draws[i][2] for i in range(t - self.seq_len, t)]
        X = torch.stack([draw_set_to_multi_hot(s) for s in seq_draws], dim=0)
        # y: draws[t] as (10000,)
        y = draw_set_to_multi_hot(self.draws[t][2])
        return X, y


class RMSNorm(nn.Module):
    """Root-mean-square normalization (LLaMA/SOTA). Lighter than LayerNorm, stable in deep nets."""

    def __init__(self, dim: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)
        return (x * rms) * self.weight


class SwiGLUFFN(nn.Module):
    """SwiGLU feed-forward (gate * silu(up)); better accuracy per parameter than standard ReLU/GELU FFN."""

    def __init__(self, d_model: int, dim_feedforward: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.gate = nn.Linear(d_model, dim_feedforward)
        self.up = nn.Linear(d_model, dim_feedforward)
        self.down = nn.Linear(dim_feedforward, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.down(torch.nn.functional.silu(self.gate(x)) * self.up(x)))


class SotaEncoderLayer(nn.Module):
    """
    Encoder layer with pre-norm, RMSNorm, and SwiGLU FFN (SOTA 2025–2026).
    Improves accuracy and training stability; works with PyTorch SDPA in MHA.
    """

    def __init__(
        self,
        d_model: int,
        nhead: int,
        dim_feedforward: int = 1024,
        dropout: float = 0.1,
        batch_first: bool = True,
    ) -> None:
        super().__init__()
        self.norm1 = RMSNorm(d_model)
        self.self_attn = nn.MultiheadAttention(
            d_model, nhead, dropout=dropout, batch_first=batch_first
        )
        self.norm2 = RMSNorm(d_model)
        self.ffn = SwiGLUFFN(d_model, dim_feedforward, dropout)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        src: torch.Tensor,
        src_mask: torch.Tensor | None = None,
        src_key_padding_mask: torch.Tensor | None = None,
        is_causal: bool | None = None,
    ) -> torch.Tensor:
        # Pre-norm attention
        x = src + self._attn_block(src, src_mask, src_key_padding_mask)
        # Pre-norm SwiGLU FFN
        x = x + self.ffn(self.norm2(x))
        return x

    def _attn_block(
        self,
        src: torch.Tensor,
        src_mask: torch.Tensor | None,
        src_key_padding_mask: torch.Tensor | None,
    ) -> torch.Tensor:
        s = self.norm1(src)
        out, _ = self.self_attn(s, s, s, attn_mask=src_mask, key_padding_mask=src_key_padding_mask)
        return self.dropout(out)


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for transformer."""

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1) -> None:
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, d_model)
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


class NextDrawTransformer(nn.Module):
    """
    Encoder-only transformer: sequence of past draws -> logits over 10k numbers.
    - Input (B, L, 10000) -> linear to (B, L, d_model) -> pos -> encoder -> last step -> (B, d_model) -> linear -> (B, 10000).
    """

    def __init__(
        self,
        seq_len: int,
        d_model: int = 256,
        nhead: int = 8,
        num_encoder_layers: int = 4,
        dim_feedforward: int = 1024,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.seq_len = seq_len
        self.d_model = d_model
        self.input_proj = nn.Linear(N_NUMBERS, d_model)
        self.pos_encoder = PositionalEncoding(d_model, max_len=seq_len + 1, dropout=dropout)
        self.transformer_encoder = nn.ModuleList([
            SotaEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                batch_first=True,
            )
            for _ in range(num_encoder_layers)
        ])
        self.head = nn.Linear(d_model, N_NUMBERS)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, L, 10000) multi-hot sequence of L draws.
        Returns: (B, 10000) logits for next draw.
        """
        # (B, L, d_model)
        x = self.input_proj(x)
        x = self.pos_encoder(x)
        # (B, L, d_model)
        for layer in self.transformer_encoder:
            x = layer(x)
        enc = x
        # Use last timestep
        last = enc[:, -1, :]  # (B, d_model)
        logits = self.head(last)  # (B, 10000)
        return logits


def predict_top_k(model: NextDrawTransformer, x: torch.Tensor, k: int = 23) -> list[list[int]]:
    """
    x: (B, L, 10000). Returns list of B lists of k indices (top-k per batch item).
    """
    model.eval()
    with torch.no_grad():
        logits = model(x)
        # (B, 10000) -> topk per row
        _, indices = torch.topk(logits, k, dim=-1)
    return indices.cpu().tolist()
