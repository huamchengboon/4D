# 24-number strategy: data-driven backtest result

## Constraint

- Choose **exactly 24 numbers** per draw.
- **Same 24 numbers** for every draw and every operator in a given backtest.
- Bet **RM1 on each number** each draw → cost **RM 24 per draw**.
- Prizes: **4D Big** (1st 2500, 2nd 1000, 3rd 500, Special 180, Consolation 60) **+ 3D Big** (last 3 digits match 1st/2nd/3rd: 250, 210, 150). One prize per number per draw (best match only).

---

## Best strategy: Top 24 individual numbers

**Task:** Pick the **24 individual numbers** (from 0000–9999) that together make the most profit. They may or may not be from one multiset.

**Method:** Precompute 4D+3D total winnings for each number 0–9999 over all draws. For each number, profit = winnings − n_draws. Sort by profit descending; take the top 24. Combined profit = sum of their winnings − 24×n_draws.

**Result (all operators, 17,751 draws):**  
- **Cost:** RM 426,024  
- **Winnings:** RM 871,740  
- **Profit: +445,716 RM**

**The 24 numbers:**  
0717, 1113, 1990, 2483, 2899, 2965, 3184, 3869, 3887, 4092, 4427, 4479, 4681, 5122, 5180, 5194, 5451, 6554, 7605, 8844, 8992, 9039, 9527, 9844

These are the 24 most profitable numbers when bet RM1 each per draw (4D+3D); they are not the 24 permutations of a single multiset.

---

## Hypothesis 1: Best multiset (24 = permutations of one multiset)

**Reasoning:**  
Among 210 multisets (4 distinct digits), each has 24 permutations. We scan all 210 with 4D+3D and pick the multiset with highest total profit (constraint: 24 numbers must be that multiset’s permutations).

**Result:**  
- **Best multiset: 1237**
- **24 numbers:** all permutations of 1,2,3,7 (1237, 1273, 1327, …).
- **Profit: +129,106 RM** (all operators).

So the **best 24 numbers under the “one multiset” constraint** is 1237; the **best 24 with no constraint** is the individual list above (**+445,716**).

---

## Best 24 numbers per operator

If you want **per-operator** best 24 (each operator’s draws only, its own top 24):

```bash
uv run python -m analysis.strategy_24 --by-operator
```

Example (backtest): **Magnum 4D** and **Sports Toto 4D** and **Da Ma Cai 1+3D** each get a different set of 24 numbers and each is profitable (e.g. Magnum +269,720, Sports Toto +245,802, Da Ma Cai +262,364). The 24 numbers are listed in the output per operator.

---

## How to reproduce

```bash
# Both strategies (precompute once, then best multiset + top 24 individual)
uv run python -m analysis.strategy_24

# Best 24 numbers per operator (Magnum, Sports Toto, Da Ma Cai)
uv run python -m analysis.strategy_24 --by-operator

# With operator filter (e.g. Magnum only)
uv run python -m analysis.strategy_24 --operator "Magnum 4D"

# No progress bars
uv run python -m analysis.strategy_24 --quiet
```

---

## Caveat

Backtest uses historical data. Past profit does not guarantee future profit; the game has a structural house edge. The “top 24 individual” set is chosen by historical 4D+3D performance; 9844 appears in that set (it had unusually many 1st-prize hits in history).
