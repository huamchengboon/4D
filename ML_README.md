# 4D Data Analysis & “Prediction” – Summary and Recommendation

## 1. Data analysis

### 1.1 What we did

- **Load & shape**: 17,751 draw records (Magnum, Da Ma Cai, Sports Toto); 408,247 individual number records in long format (date, operator, prize_type, number).
- **Uniformity (χ² test)**: Over 0000–9999, the observed counts are **consistent with a uniform distribution** (p ≈ 0.97). We do not reject uniformity at α = 0.05.
- **First-digit (0–9)**: First-digit distribution **does** differ from equal 10% (p ≈ 0). That’s expected (e.g. leading zeros in 4D, different digit usage); it does **not** imply predictability of the next draw.
- **Independence**: Lag-1 autocorrelation of 1st prize (as integer) over time is **≈ 0.0005**. So past 1st prizes do not usefully predict the next one.

### 1.2 Conclusion from EDA

- The data look like **uniform(0000–9999)** draws with **no meaningful temporal dependence**.
- There is **no evidence of exploitable structure** for predicting the next winning number.

---

## 2. “Best” model for this type of data

### 2.1 Type of problem

- **Target**: Next 4D outcome(s) (e.g. 1st prize, or a set of 23 numbers).
- **Input**: Only historical draws (and optionally metadata like date/operator).
- **Structure**: Categorical outcomes (0000–9999), no causal link from past to future.

### 2.2 Why ML does not help

- Draws are **designed to be random and independent** (physical/PRNG process).
- **No model** (linear, tree, neural net, etc.) can extract signal that isn’t there.
- Fitting complex models (LSTM, transformer, etc.) will:
  - Fit **noise**, not structure.
  - Not generalize: holdout “hit rate” will match **random chance** (as in our evaluation below).

So the **best model** in a strict sense is the one that matches the data-generating process and does not claim false predictability: **uniform over 0000–9999**, or at most **empirical frequency** as a marginal distribution (which still does **not** improve prediction of the next draw).

### 2.3 Recommended “models” (baselines only)

| Model | Description | Use |
|--------|-------------|-----|
| **Uniform** | Sample uniformly from 0000–9999 | Theoretically correct if draws are fair; no data needed. |
| **Empirical frequency** | Sample proportional to historical counts | Matches marginal distribution; **does not** improve prediction. |
| **Top‑K “hot numbers”** | Always output the K most frequent numbers | Deterministic baseline; no predictive advantage. |

We **do not** recommend:

- Any ML model (NN, LSTM, XGBoost, etc.) for “predicting” next numbers.
- Treating hit rate on holdout as evidence of predictive power when it is consistent with random chance.

---

## 3. Evaluation (holdout test)

- **Setup**: Last ~5% of dates as holdout; for each holdout draw we ask: “Does the model’s set of 23 numbers contain the actual 1st prize?”
- **Expected** if guessing at random: 23/10000 ≈ **0.0023** per draw.
- **Observed** (example run):
  - UniformPredictor: 2/1074 ≈ 0.0019  
  - EmpiricalFrequencyPredictor: 2/1074 ≈ 0.0019  
  - TopKFrequencyPredictor: 2/1074 ≈ 0.0019  

So all three baselines perform **in line with random chance**. No model “beats” the other in a statistically meaningful way for prediction.

---

## 4. How to run

```bash
# EDA + baseline comparison (recommended)
uv run python -m analysis.run_ml

# Optional: custom CSV and test ratio
uv run python -m analysis.run_ml --csv path/to/4d_history.csv --test-ratio 0.1
```

- **EDA**: `analysis/eda.py` – `run_eda()`, `print_eda_report()`.
- **Baselines**: `analysis/models.py` – `UniformPredictor`, `EmpiricalFrequencyPredictor`, `TopKFrequencyPredictor`, `evaluate_predictor()`, `run_model_comparison()`.

---

## 5. RL fine-tuning and why hit rate stays low

The RL policy uses research-backed techniques: count reward, running baseline, entropy bonus, optional recency-weighted state. These can nudge backtest hit rate (e.g. ~5% → ~6–7%) but do not create real predictability—lottery draws remain random.

---

## 6. One-line answer

**Best “model” for this data if you must output “next numbers”:**  
Use **uniform random over 0000–9999** (or, for a data-based marginal only, empirical frequency). **No machine learning model is appropriate for actually predicting the next winning numbers**; the data and evaluation show that “prediction” is no better than random chance.
