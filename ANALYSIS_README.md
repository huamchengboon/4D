# 4D History Data Analysis

Data engineering and visualization for `4d_history.csv` using **Polars** (fast) and **Seaborn**/Matplotlib.

## Stack

| Layer        | Tool        | Role                          |
|-------------|-------------|-------------------------------|
| Data load   | Polars      | Fast CSV read, typed columns  |
| Transform   | Polars      | Long format, frequencies      |
| Viz         | Seaborn     | Themed plots                  |
| Backend     | Matplotlib  | Figure export / Agg           |
| Interop     | PyArrow     | Polars → Pandas for Seaborn   |

Polars is used for all data work; conversion to Pandas only at plot time.

## Setup

Dependencies are in `pyproject.toml`:

```bash
uv sync
```

## Run full pipeline

Generate summary stats and all plots into `output/`:

```bash
uv run python -m analysis.run_analysis
# optional: custom CSV path
uv run python -m analysis.run_analysis --csv path/to/4d_history.csv
```

**Outputs:**

- `output/draws_per_day.png` – Draws per calendar day over time
- `output/operator_breakdown.png` – Count by operator (Magnum, Da Ma Cai, Sports Toto)
- `output/number_frequency.png` – Top 30 most frequently drawn 4D numbers
- `output/first_digit_dist.png` – First-digit distribution (0–9)
- `output/prize_type_breakdown.png` – Count by prize type (1st, 2nd, 3rd, special, consolation)

## Use in code or notebook

```python
from analysis import (
    load_history,
    get_draws_long,
    get_number_frequencies,
    plot_number_frequency_single,
    plot_first_digit_distribution,
)

# Load (Polars DataFrame)
df = load_history()  # uses 4d_history.csv next to project root
# df = load_history("path/to/4d_history.csv")

# Long format: one row per (date, operator, draw_no, prize_type, number)
long = get_draws_long(df)

# Frequency of each 4D number
freq = get_number_frequencies(df)
freq_by_op = get_number_frequencies(df, by_operator=True)

# Plots (optional save= path to save PNG)
plot_number_frequency_single(freq, top_n=20, save="output/top20.png")
plot_first_digit_distribution(long, save="output/digits.png")
```

## Schema (raw CSV)

| Column       | Type   | Description                          |
|-------------|--------|--------------------------------------|
| date        | Date   | Draw date (YYYY-MM-DD)               |
| operator    | str    | Magnum 4D, Da Ma Cai 1+3D, Sports Toto 4D |
| draw_no     | str    | e.g. 337/26                          |
| 1st, 2nd, 3rd | str  | Top 3 prize numbers (4 digits)       |
| special     | str    | Comma-separated special numbers      |
| consolation | str    | Comma-separated consolation numbers  |

Long format adds `prize_type` (1st, 2nd, 3rd, special, consolation) and one `number` per row.

## ML and “prediction”

Lottery draws are effectively **random and independent**. EDA and baseline evaluation are in `analysis/eda.py` and `analysis/models.py`. Run:

```bash
uv run python -m analysis.run_ml
```

See **ML_README.md** for: statistical findings, why no ML model can predict next numbers, and the recommended “model” (uniform or empirical baseline only).

## Reinforcement learning (reward / punish backtest)

An RL policy is trained by backtesting over the full history: **reward +1** when at least one of the model's 23 predicted numbers appears in the actual draw, **punish -1** when none match. State = empirical frequency from past draws; policy = small NN; action = sample 23 numbers. Training is REINFORCE over the whole history.

```bash
uv run python -m analysis.run_rl
uv run python -m analysis.run_rl --max-draws 500 --epochs 1   # quick test
```

**Checkpoints:** By default the policy is saved to `output/rl_checkpoint.pt` after each epoch and at the end. To **resume** and keep improving the same model:

```bash
uv run python -m analysis.run_rl --resume output/rl_checkpoint.pt --epochs 5
```

Use `--checkpoint PATH` to change where to save; use `--no-save` to disable saving (fresh run, no checkpoint).

**Device:** Training uses the best available device automatically: **CUDA** (NVIDIA GPU), then **MPS** (Apple Silicon GPU), then CPU. On Apple Silicon, PyTorch uses Metal (MPS) for acceleration. Force a device with `--device mps` or `--device cpu`.

**Tuning (research-backed):** The default setup uses strategies from the RL literature to improve learning:
- **Reward:** `--reward prize` (default) uses **actual Magnum prize scale**: reward = (winnings − 23) RM so 1st (2500) is rewarded much more than special (180) or consolation (60). Alternatives: `count` (n_hits) or `binary` (+1/-1).
- **Architecture:** Default **3 hidden layers** (512, 256, 256); override with `--hidden 512,256,256`. See **docs/RL_ARCHITECTURE.md** for the math and design.
- **Baseline:** Running exponential-average baseline (`--baseline-ema 0.99`) reduces variance in REINFORCE (policy gradient).
- **Entropy bonus:** `--entropy 0.01` encourages exploration and avoids early collapse to a suboptimal policy.
- **Recency:** `--recency-decay 0.99` (e.g.) weights recent draws more in the state (optional; off by default).
- **Attention over past draws:** `--seq-len 32` (e.g.) makes the model see a **time-series** of the last N draws. Each draw is encoded as multi-hot; a small transformer (multi-head self-attention) runs over the sequence so the policy is aware of *which* numbers appeared *when*, not just aggregate frequency. Use `--seq-dim 128` to set the attention embedding size.

Example: `uv run python -m analysis.run_rl --reward prize --entropy 0.02 --seq-len 32`

Options: `--csv`, `--epochs`, `--k`, `--lr`, `--device`, `--max-draws`, `--checkpoint`, `--resume`, `--no-save`, `--log-every`, `--quiet`, `--reward`, `--hidden`, `--entropy`, `--baseline-ema`, `--recency-decay`, `--seq-len`, `--seq-dim`.

**Hyperparameter tuning:** Use Optuna to search over lr, entropy, baseline_ema, recency_decay, hidden sizes, and seq_len/seq_dim; the objective is **maximize final-eval profit (RM)**. Run a short tuning phase (e.g. 20 trials on 2000 draws, 2 epochs per trial), then train the full run with the best params:

```bash
uv run python -m analysis.run_rl_tune --trials 20 --max-draws 2000 --epochs 2
uv run python -m analysis.run_rl_tune --trials 10 --quiet --save-best output/best_params.json
```

Tuning uses TPE (Tree-structured Parzen Estimator) for sample-efficient search. After tuning, the script prints the best params and a ready-to-paste `run_rl` command. Use `--save-best PATH` to write the best params to JSON.

**Evolution Strategies (ES):** Gradient-free alternative to REINFORCE. Perturb policy parameters with Gaussian noise, evaluate fitness (total reward over backtest), update the mean by reward-weighted average of perturbations. Useful when rewards are sparse/noisy.

```bash
uv run python -m analysis.run_rl_es --generations 30 --workers 8 --sigma 0.02 --lr 0.01
uv run python -m analysis.run_rl_es --max-draws 365 --generations 20 --workers 4 --resume output/rl_es_checkpoint.pt
uv run python -m analysis.run_rl_es --elitist   # keep best worker when it beats the updated mean
```

Use `--elitist` to use genetic-style selection: after each generation, if the best worker's reward is higher than the updated mean's reward, the next generation starts from that best worker's parameters instead of the mean.

Use `--resample-draws` (with `--max-draws`) so each generation sees a new random subset of draws; reduces overfitting to one fixed set (fitness is noisier but policy generalizes better).

**Overfit mode:** If ES isn't improving, try intentionally overfitting to a fixed subset: `--overfit` uses the same 200 draws (seed 42) every generation and runs 80 generations (ES) or 50 epochs (RL). Same for REINFORCE: `uv run python -m analysis.run_rl --overfit` trains on a fixed 200 draws for 50 epochs.

Checkpoint path: `output/rl_es_checkpoint.pt` (use `--checkpoint PATH` or `--no-save` to disable).

---

**Transformer (next-draw prediction):** Supervised model: input = sequence of past draws (multi-hot), output = logits over 10k numbers; train with BCE, take top-23 as prediction. Much faster than RL/ES; single forward pass per sample.

```bash
uv run python -m analysis.run_transformer --seq-len 64 --epochs 20 --batch-size 64
uv run python -m analysis.run_transformer --max-draws 2000 --epochs 10 --d-model 256 --layers 4
```

Options: `--seq-len`, `--d-model`, `--nhead`, `--layers`, `--dim-ff`, `--dropout`, `--epochs`, `--batch-size`, `--lr`, `--val-ratio`, `--checkpoint`. Checkpoint: `output/transformer_4d.pt`.

**Backtest (eval only):** Load a saved model and evaluate on the last N draws (hit rate + P&L, RM1 per number):

```bash
uv run python -m analysis.run_transformer --backtest --checkpoint output/transformer_4d.pt
uv run python -m analysis.run_transformer --backtest --backtest-draws 2000
```
