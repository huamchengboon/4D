# Why did 9844 make profit?

## Short answer

**9844 made profit because it won 1st prize 10 times** in the historical data—far more than expected under a uniform draw. That outlier in top-tier wins is almost entirely why it is the most profitable number in the backtest.

---

## Backtest result (RM1 straight every draw, all operators)


| Metric             | Value       |
| ------------------ | ----------- |
| Total draws        | 17,751      |
| Cost (RM1 × draws) | 17,751      |
| Total winnings     | 31,040      |
| **Profit**         | **+13,289** |


---

## Hit breakdown for 9844


| Prize type  | Hits   | Prize per hit (RM) | Contribution (RM) |
| ----------- | ------ | ------------------ | ----------------- |
| **1st**     | **10** | 2,500              | **25,000**        |
| 2nd         | 0      | 1,000              | 0                 |
| 3rd         | 5      | 500                | 2,500             |
| Special     | 14     | 180                | 2,520             |
| Consolation | 17     | 60                 | 1,020             |
| **Total**   | 46     |                    | **31,040**        |


About **80% of the winnings** (25,000 of 31,040) come from **1st prize alone**.

---

## Expected vs observed (uniform draw)

If each of the 10,000 numbers were equally likely for 1st prize each draw:

- Expected 1st-prize wins per number ≈ **1.78** (17,751 ÷ 10,000).
- **9844 has 10 first-prize wins** → roughly **5.6× expected**.

Under that uniform model:

- P(a given number gets ≥10 first prizes) ≈ **0.000017** (about 1 in 58,000).
- In the full dataset, **9844 is the only number** with 10 first-prize wins; all others have 9 or fewer.

So 9844 is an extreme positive outlier in 1st-prize frequency, not a “special” number by digit pattern or operator.

---

## When and where did 9844 win 1st?

All 10 first-prize wins (date, operator):


| Date       | Operator       |
| ---------- | -------------- |
| 1987-08-09 | Magnum 4D      |
| 1997-02-23 | Sports Toto 4D |
| 1999-06-23 | Da Ma Cai 1+3D |
| 2001-04-18 | Da Ma Cai 1+3D |
| 2011-03-12 | Sports Toto 4D |
| 2012-05-27 | Da Ma Cai 1+3D |
| 2015-03-25 | Sports Toto 4D |
| 2017-09-27 | Da Ma Cai 1+3D |
| 2017-11-29 | Da Ma Cai 1+3D |
| 2025-01-18 | Sports Toto 4D |


Wins are spread across **all three operators** and over **decades** (1987–2025)—no single operator or short period explains the total.

---

## Conclusion

- **Why 9844 made profit:** It won **1st prize 10 times** (≈5.6× the expected rate under uniformity), and 1st prize pays 2,500 per RM1 bet. That concentration of top-tier wins dominates its P&L.
- **Is it “lucky” or “predictable”?** In this dataset it behaves like **random variance**: one number had to be the luckiest in 1st-prize count; that number turned out to be 9844. There is no evidence here of a structural bias (e.g. digit pattern or operator) that would make 9844 more likely to win in the future.
- **Takeaway:** 9844’s backtest profit is **past luck**, not a reliable edge. Going forward, each number’s expected return is still set by the game’s odds and prize structure; historical outliers like 9844 do not imply future outperformance.

