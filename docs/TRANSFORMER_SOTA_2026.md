# Transformer State of the Art (as of 2026)

Summary of recent architecture and efficiency advances relevant to sequence prediction (e.g. 4D next-draw).

---

## 1. Architecture (accuracy & stability)

| Component | SOTA (2025–2026) | Notes |
|-----------|-------------------|--------|
| **Normalization** | **RMSNorm** (pre-norm) | Simpler than LayerNorm; standard in LLaMA, Supernova. Use **norm_first=True** (pre-norm) for stability. |
| **Position** | **RoPE** (Rotary Position Embeddings) | Relative positions; better length generalization. Used in Supernova, Nemotron-H. |
| **FFN** | **SwiGLU** | Gated linear unit: `(W₁x)·σ(W₂x)` instead of `σ(Wx)`. Better quality per parameter (Supernova, LLaMA). |
| **Attention** | **GQA** (Grouped Query Attention) | Fewer K/V heads than Q heads (e.g. 3:1); less memory, similar quality. |

**Papers:** Supernova (arXiv:2507.15773), AdaPerceiver (2511.18105), STEM (2601.10639).

---

## 2. Efficiency (speed & long context)

| Approach | Idea | Benefit |
|----------|------|---------|
| **Hybrid Mamba–Transformer** | Mix SSM (Mamba) layers with attention | ~3× faster inference, O(L) per Mamba block; e.g. Nemotron-H, Samba. |
| **Sparse / linear attention** | Sparse attention or linear attention (e.g. ZeroS) | Sub-quadratic or O(N); e.g. SCOUT, MiniCPM-SALA (sparse+linear 1:3). |
| **Dynamic token routing** | Route only a fraction of tokens through full attention | DTRNet: ~10% of tokens through attention, rest get light updates; scales with length. |
| **Segment compression** | Compress segments then attend over compressed tokens | SCOUT: sub-quadratic memory, on par with full attention at 400M–1.3B. |
| **Embedding modules (STEM)** | Replace FFN up-projection with embedding lookups | Fewer FFN params, 3–4% accuracy gain in reported setups. |

**Papers:** Nemotron-H (2504.03624), Gecko (2601.06463), SCOUT (2509.00935), DTRNet (2509.00925), Hybrid Dual-Path Linear (2602.07070), ZeroS linear attention (2602.05230).

---

## 3. Training & inference stack

| Topic | SOTA (2025–2026) |
|-------|-------------------|
| **Attention backend** | PyTorch **SDPA** (uses FlashAttention-2/3 when available). `nn.TransformerEncoder` uses it by default where applicable. |
| **Precision** | **FP16/BF16** training; **FP8** for inference on H100+ (FlashAttention-3). |
| **Compile** | **torch.compile(model)** for extra speed (PyTorch 2+). |
| **LR schedule** | **OneCycleLR** or cosine; warmup common. |

---

## 4. Time-series / sequence prediction

- **Patch tokenization** (group consecutive steps) often beats point-wise tokens.
- **Pre-norm** and **relative position** (e.g. RoPE) help long sequences.
- **Multi-resolution** (e.g. different patch sizes) can capture multiple scales.
- **Bidirectional** encoders can outperform decoder-only for some forecasting setups (e.g. LTSF).

**Papers:** Timer-XL (2410.04803), “Power of Architecture” LTSF (2507.13043).

---

## 5. Implemented in this repo (accuracy-first)

The 4D Transformer now uses a **SOTA encoder layer** by default:

- **Pre-norm** — Normalize before attention and before FFN; more stable gradients.
- **RMSNorm** — Replaces LayerNorm in the encoder (simpler, stable in deep nets).
- **SwiGLU FFN** — Gate and up projections with SiLU; then down. Better accuracy per parameter.

Existing checkpoints saved with the old (LayerNorm + GELU FFN) architecture are **not** compatible; train from scratch or use `--no-resume` once.

## 6. What else to try (optional)

**Already done:** Pre-norm, RMSNorm, SwiGLU (see §5).

**Low effort**

- **SDPA:** PyTorch 2 uses it when possible; keep `batch_first=True`.
- **AMP + compile:** Use `--amp` (default) and `--compile` for speed.

**Higher effort (for long sequences)**

- **RoPE** instead of sinusoidal PE (custom attention or layer).
- **GQA** (custom `MultiheadAttention` with fewer K/V heads).
- **Mamba hybrid:** Add Mamba/SSM layers (e.g. alternate with attention) for O(L) scaling and faster long-context.

**References (arXiv)**

- 2507.15773 Supernova  
- 2504.03624 Nemotron-H  
- 2511.18105 AdaPerceiver  
- 2601.10639 STEM  
- 2601.06463 Gecko  
- 2509.00935 SCOUT  
- 2602.05230 ZeroS  
- 2602.07070 Hybrid Dual-Path Linear  
