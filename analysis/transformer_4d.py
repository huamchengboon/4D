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


def _apply_rope(q: torch.Tensor, k: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply rotary position embedding to Q and K. q,k: (B, H, L, D); cos, sin: (1, 1, L, D)."""
    # RoPE: rotate pairs of dimensions by position * theta
    def rotate(x: torch.Tensor) -> torch.Tensor:
        x1, x2 = x.chunk(2, dim=-1)
        return torch.cat([x1 * cos - x2 * sin, x1 * sin + x2 * cos], dim=-1)
    return rotate(q), rotate(k)


class RoPECache(nn.Module):
    """Cached cos/sin for RoPE (max_len, head_dim)."""

    def __init__(self, head_dim: int, max_len: int = 4096, base: float = 10000.0) -> None:
        super().__init__()
        inv_freq = 1.0 / (base ** (torch.arange(0, head_dim, 2, dtype=torch.float32) / head_dim))
        position = torch.arange(max_len, dtype=torch.float32)
        freqs = torch.outer(position, inv_freq)
        cos = freqs.cos().unsqueeze(0).unsqueeze(0)  # (1, 1, L, D/2)
        sin = freqs.sin().unsqueeze(0).unsqueeze(0)
        self.register_buffer("cos", cos)
        self.register_buffer("sin", sin)

    def forward(self, seq_len: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.cos[:, :, :seq_len, :], self.sin[:, :, :seq_len, :]


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


class SDPAMultiheadAttention(nn.Module):
    """
    Multi-head self-attention with optional RoPE and GQA.
    SDPA for speed; RoPE for better length; GQA for less memory.
    """

    def __init__(
        self,
        d_model: int,
        nhead: int,
        dropout: float = 0.1,
        n_kv_heads: int | None = None,
        use_rope: bool = False,
        max_len: int = 4096,
    ) -> None:
        super().__init__()
        assert d_model % nhead == 0
        self.nhead = nhead
        self.head_dim = d_model // nhead
        self.n_kv_heads = n_kv_heads if n_kv_heads is not None else nhead
        assert nhead % self.n_kv_heads == 0
        self.use_rope = use_rope and self.head_dim % 2 == 0
        self.q_proj = nn.Linear(d_model, nhead * self.head_dim)
        self.k_proj = nn.Linear(d_model, self.n_kv_heads * self.head_dim)
        self.v_proj = nn.Linear(d_model, self.n_kv_heads * self.head_dim)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout_p = dropout
        if self.use_rope:
            self.rope = RoPECache(self.head_dim, max_len=max_len)
        else:
            self.rope = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, L, _ = x.shape
        q = self.q_proj(x).view(B, L, self.nhead, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, L, self.n_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, L, self.n_kv_heads, self.head_dim).transpose(1, 2)
        if self.n_kv_heads != self.nhead:
            n_rep = self.nhead // self.n_kv_heads
            k = k.repeat_interleave(n_rep, dim=1)
            v = v.repeat_interleave(n_rep, dim=1)
        if self.use_rope and self.rope is not None:
            cos, sin = self.rope(L)
            q, k = _apply_rope(q, k, cos, sin)
        out = torch.nn.functional.scaled_dot_product_attention(
            q, k, v, dropout_p=self.dropout_p if self.training else 0.0
        )
        out = out.transpose(1, 2).contiguous().view(B, L, -1)
        return self.out_proj(out)


def _drop_path(x: torch.Tensor, drop_prob: float, training: bool) -> torch.Tensor:
    if drop_prob == 0.0 or not training:
        return x
    keep = 1 - drop_prob
    shape = (x.size(0),) + (1,) * (x.ndim - 1)
    mask = x.new_empty(shape).bernoulli_(keep).div_(keep)
    return x * mask


class SotaEncoderLayer(nn.Module):
    """
    Encoder layer: pre-norm, RMSNorm, SDPA (optional RoPE/GQA), SwiGLU, LayerScale, stochastic depth.
    """

    def __init__(
        self,
        d_model: int,
        nhead: int,
        dim_feedforward: int = 1024,
        dropout: float = 0.1,
        batch_first: bool = True,
        n_kv_heads: int | None = None,
        use_rope: bool = False,
        max_len: int = 4096,
        drop_path: float = 0.0,
        layer_scale_init: float = 0.0,
    ) -> None:
        super().__init__()
        self.norm1 = RMSNorm(d_model)
        self.self_attn = SDPAMultiheadAttention(
            d_model, nhead, dropout, n_kv_heads=n_kv_heads, use_rope=use_rope, max_len=max_len
        )
        self.norm2 = RMSNorm(d_model)
        self.ffn = SwiGLUFFN(d_model, dim_feedforward, dropout)
        self.dropout = nn.Dropout(dropout)
        self.drop_path_rate = drop_path
        self.ls1 = nn.Parameter(torch.ones(d_model) * layer_scale_init) if layer_scale_init > 0 else None
        self.ls2 = nn.Parameter(torch.ones(d_model) * layer_scale_init) if layer_scale_init > 0 else None

    def forward(
        self,
        src: torch.Tensor,
        src_mask: torch.Tensor | None = None,
        src_key_padding_mask: torch.Tensor | None = None,
        is_causal: bool | None = None,
    ) -> torch.Tensor:
        attn_out = self.dropout(self.self_attn(self.norm1(src)))
        if self.ls1 is not None:
            attn_out = attn_out * self.ls1
        x = src + _drop_path(attn_out, self.drop_path_rate, self.training)
        ffn_out = self.ffn(self.norm2(x))
        if self.ls2 is not None:
            ffn_out = ffn_out * self.ls2
        x = x + _drop_path(ffn_out, self.drop_path_rate, self.training)
        return x


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
    Supports RoPE, GQA, LayerScale, stochastic depth.
    """

    def __init__(
        self,
        seq_len: int,
        d_model: int = 256,
        nhead: int = 8,
        num_encoder_layers: int = 4,
        dim_feedforward: int = 1024,
        dropout: float = 0.1,
        n_kv_heads: int | None = None,
        use_rope: bool = False,
        drop_path: float = 0.0,
        layer_scale: float = 0.0,
        use_grad_checkpoint: bool = False,
    ) -> None:
        super().__init__()
        self.seq_len = seq_len
        self.d_model = d_model
        self.use_rope = use_rope
        self.use_grad_checkpoint = use_grad_checkpoint
        self.input_proj = nn.Linear(N_NUMBERS, d_model)
        self.pos_encoder = None if use_rope else PositionalEncoding(d_model, max_len=seq_len + 1, dropout=dropout)
        max_len = seq_len + 1
        layer_drop_paths = [
            drop_path * (i / max(num_encoder_layers - 1, 1)) for i in range(num_encoder_layers)
        ]
        self.transformer_encoder = nn.ModuleList([
            SotaEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                batch_first=True,
                n_kv_heads=n_kv_heads,
                use_rope=use_rope,
                max_len=max_len,
                drop_path=layer_drop_paths[i],
                layer_scale_init=layer_scale,
            )
            for i in range(num_encoder_layers)
        ])
        self.head = nn.Linear(d_model, N_NUMBERS)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_proj(x)
        if self.pos_encoder is not None:
            x = self.pos_encoder(x)
        for layer in self.transformer_encoder:
            if self.training and self.use_grad_checkpoint:
                x = torch.utils.checkpoint.checkpoint(layer, x, use_reentrant=False)
            else:
                x = layer(x)
        last = x[:, -1, :]
        return self.head(last)


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
