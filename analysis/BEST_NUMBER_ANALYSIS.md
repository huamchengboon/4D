# Best number analysis — backtest-driven

## What we did

1. **Full scan (210 multisets)**  
   All 4-digit combinations with 4 distinct digits (e.g. 0123, 1347) were backtested with:
   - **Straight (combo)**: RM 1 on each of the 24 permutations = RM 24 per draw. Prizes: 1st 2500, 2nd 1000, 3rd 500, Special 180, Consolation 60.
   - **i-box**: RM 1 per draw (one bet covering 24 permutations). Prizes: 1st 105, 2nd 42, 3rd 21, Special 8, Consolation 3.
   - Data: all operators (Magnum 4D, Sports Toto 4D, Da Ma Cai), full history.

2. **By-year and recent window**  
   For each multiset we computed total P&L, number of years with profit, and (for straight) P&L in the last 5 years.

3. **Conditional rule**  
   “Bet only in years after a profit year” was tested for several top multisets; it reduced loss but did not turn total P&L positive.

## Result: no consistently profitable number

- **No multiset has total profit > 0** over the full history for either straight (RM24/draw) or i-box (RM1/draw). The game has a structural house edge; every number loses in expectation over the long run.
- Over **last 10 years** only, every multiset still has negative total P&L; best (least loss) in that window is **2478** (straight, all operators).

## Best we can pick from backtest

If we still want a single “best” number by historical performance:

| Criterion | Number | Backtest result |
|-----------|--------|------------------|
| **Best total P&L (least loss)** | **1237** | Straight: RM -101,624 total; 8 years with profit. i-box: RM -3,731 total. |
| **Most years with profit** | **4789** (or 1459, 0259) | 10 years with profit; total P&L worse than 1237 (e.g. 4789: -121,564). |
| **Best recent 5 years (least loss)** | **2478** | Straight last 5y: -2,648 (still loss). |

So:

- For **“least bad” overall**: **1237** is the backtest-best choice (smallest total loss, 8 profit years).
- For **“most often profitable by year”**: **4789** (10 profit years out of 42), but total P&L is more negative than 1237.

## How to reproduce

```bash
# Scan all 210 multisets, report top 20 by total P&L and by profit years
uv run python -m analysis.backtest_ibox --find-best --all-operators

# Single-number straight backtest (e.g. 1237)
uv run python -m analysis.backtest_ibox --number 1237 --combo --all-operators

# By-year breakdown for 1237
uv run python -m analysis.backtest_ibox --number 1237 --combo --by-year --all-operators
```

## Conclusion

No number is **consistently profitable** in the sense of total P&L > 0 over the full backtest. The number that **loses the least** and still has **multiple profit years** in the backtest is **1237**.
