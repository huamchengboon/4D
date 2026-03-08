# What the RL Model Controls and What You Can Change

## 1. What the model controls (its “action”)

The **policy** has a single decision each step:

- **Input (state):**  
  - **Frequency vector** (10,000 dim): normalized counts of how often each number 0000–9999 appeared in past draws.  
  - **Optional sequence:** last `seq_len` draws (multi-hot), encoded with attention (when `--seq-len > 0`).
- **Output (action):** A **probability distribution over all 10,000 numbers** (logits → softmax).
- **What gets “chosen”:** We **sample 23 numbers without replacement** from that distribution. Those 23 are the model’s “predictions” (bets) for that draw.

So the model only controls **which 23 numbers to pick** each draw. It does **not** control:

- How many numbers to pick (fixed at **K**, default 23).
- Stake per number (that’s for P&L only; the RL reward is hit/miss or hit count).
- Which draw or which operator; it just sees the next draw in the backtest order.

---

## 2. Parameters you can change (CLI)

All of these are set when you run `uv run python -m analysis.run_rl`:

| Argument | Default | What it does |
|----------|--------|----------------|
| **--epochs** | 3 | Number of full passes over the history (training + final eval). |
| **--k** | 23 | Numbers to predict per draw (same as “23 picks” in the summary). |
| **--lr** | 1e-3 | Learning rate for the policy (Adam). |
| **--device** | auto | `cuda`, `mps`, or `cpu`. Auto picks MPS/CUDA if available. |
| **--max-draws** | None | Cap how many draws to use (for quick runs). |
| **--reward** | prize | `binary`, `count`, or `prize` (RM winnings − cost; 1st >> special >> consolation). |
| **--hidden** | 512,256,256 | Hidden layer sizes (comma-separated); default 3 layers. |
| **--entropy** | 0.01 | Entropy bonus coefficient (exploration). |
| **--baseline-ema** | 0.99 | EMA for the running baseline (variance reduction). |
| **--recency-decay** | 0 | If in (0,1), state uses exponential decay so recent draws weigh more. |
| **--seq-len** | 0 | If > 0, use attention over last N draws (time-series state). |
| **--seq-dim** | 128 | Attention embedding size when `--seq-len > 0`. |
| **--prize-weighted-state** | False | State = prize-weighted history (1st=2500, 2nd=1000, …). Use with `--reward prize`; needs prize data. |
| **--checkpoint** | output/rl_checkpoint.pt | Where to save the policy. |
| **--resume** | None | Path to checkpoint to continue training. |
| **--no-save** | False | Do not save a checkpoint. |
| **--log-every** | 500 | Print progress every N steps. |
| **--quiet** | False | Less output. |
| **--csv** | 4d_history.csv | Path to history CSV. |

So: **training/task** (epochs, k, lr, device, max_draws), **reward/learning** (reward, entropy, baseline-ema, recency-decay), **state** (seq-len, seq-dim), and **run** (checkpoint, resume, no-save, log-every, quiet, csv) are all under your control via the CLI.

---

## 2b. Does the RL model benefit from knowing which number won how much?

**Yes, in two ways:**

1. **Through the reward (already in use with `--reward prize`)**  
   When `reward_mode="prize"`, the reward each step is **RM winnings − cost** (e.g. hit 1st → +2,477, hit special → +157, hit consolation → +37). The policy gradient is larger when the model hits high-value numbers, so it is trained to favor actions that lead to bigger payouts, not just “any hit.”

2. **Through the state (optional: `--prize-weighted-state`)**  
   By default, the state is “how often each number appeared” (all tiers count the same). With `--prize-weighted-state`, the state is built from **prize-weighted counts**: 1st adds 2500, 2nd 1000, 3rd 500, special 180, consolation 60. So the model **sees** which numbers have historically been high-value in the input, not only in the reward. Use with `--reward prize` and ensure prize data is loaded (same as for P&L).

---

## 3. Parameters only in code (not in CLI)

These are fixed in `analysis/rl.py` unless you edit the code:

| What | Value | Where |
|------|--------|--------|
| **Policy MLP hidden size** | 256 | `PolicyNetwork(hidden=256)` |
| **Policy dropout** | 0.1 | `PolicyNetwork(dropout=0.1)` |
| **Attention heads** | 4 | `DrawSequenceEncoder(n_heads=4)` |
| **Attention dropout** | 0.1 | `DrawSequenceEncoder(dropout=0.1)` |
| **Grad clip** | 1.0 | `clip_grad_norm_(..., 1.0)` in backtest |
| **Reward scale** | +1 / -1 or count | `REWARD_HIT`, `REWARD_MISS`; count = raw n_hits |

So the **model size** (hidden, dropout, n_heads) and **optimization** (grad clip, reward scale) are currently not exposed as CLI flags; you’d change them in code or add new arguments.

---

## 4. What the model does *not* control

- **Prize amounts** (Magnum 1st/2nd/3rd/special/consolation) — fixed; used for reward (when `--reward prize`), optional state (`--prize-weighted-state`), and P&L reporting.
- **Which draws exist** — fixed by the CSV / `--max-draws`.
- **Order of draws** — same as in the data (e.g. by date/operator).
- **Rule “bet RM1 per number”** — that’s only for the final Cost/Winnings/Profit table, not for the RL reward.

---

## 5. One-line summary

**The RL model only chooses which 23 numbers to pick each draw.** You change *how* it learns and *what* it sees via CLI (epochs, k, lr, reward, entropy, baseline-ema, recency-decay, seq-len, seq-dim, etc.); model size and a few training details are in code only.
