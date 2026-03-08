# 24-number strategy: data-driven backtest result

## Constraint

- Choose **exactly 24 numbers** per draw.
- **Same 24 numbers** for every draw and every operator in a given backtest.
- Bet **RM1 on each number** each draw → cost **RM 24 per draw**.
- Prizes: **4D Big** (1st 2500, 2nd 1000, 3rd 500, Special 180, Consolation 60) **+ 3D Big** (last 3 digits match 1st/2nd/3rd: 250, 210, 150). One prize per number per draw (best match only).

---

## Hypothesis 1: Best multiset (24 permutations)

**Reasoning:**  
We have 210 multisets (4 distinct digits). Each multiset has 24 permutations (4!); betting all 24 gives full coverage of that digit set. From earlier analysis, **1237** was the number with the **least loss** in 4D-only backtests. Including **3D** (last 3 digits) adds payouts when our number does not match 4D but its last 3 digits match 1st/2nd/3rd. So we scan all 210 multisets with **4D+3D** and pick the one with highest total profit.

**Backtest:**  
For each multiset, 24 numbers = all permutations. Cost = 24 × n_draws. Winnings = sum over draws and over 24 numbers of (4D prize or 3D prize, best only). Operator filter: none (all operators).

**Result:**  
- **Best multiset: 1237**
- **24 numbers:** 1237, 1273, 1327, 1372, 1723, 1732, 2137, 2173, 2317, 2371, 2713, 2731, 3127, 3172, 3217, 3271, 3712, 3721, 7123, 7132, 7213, 7231, 7312, 7321 (all permutations of 1,2,3,7).
- **All operators:** 17,751 draws → Cost RM 426,024 | Winnings RM 555,130 → **Profit +129,106 RM**.
- **Per operator (same 24 numbers):**  
  - Magnum 4D: **+38,190**  
  - Sports Toto 4D: **+51,872**  
  - Da Ma Cai 1+3D: **+39,044**

**Conclusion:** Hypothesis 1 is **profitable** in the backtest. The same fixed set of 24 numbers (all permutations of 1237) is profitable across all operators.

---

## How to reproduce

```bash
# Best multiset only (fast)
uv run python -m analysis.strategy_24

# With operator filter (e.g. Magnum only)
uv run python -m analysis.strategy_24 --operator "Magnum 4D"

# Also run Hypothesis 2 (top 24 individual numbers; slow)
uv run python -m analysis.strategy_24 --top24
```

---

## Caveat

Backtest uses historical data. Past profit does not guarantee future profit; the game has a structural house edge. The result is driven by 3D payouts (last-3 match) and the choice of a multiset that historically had strong 4D performance (1237).
