# 4D History — Pattern Analysis Summary

Analysis of `4d_history.csv` using Polars and SciPy (chi-square tests, correlation). Run: `uv run python -m analysis.pattern_analysis`.

## Data

- **Rows (draws):** ~17.7k  
- **Number observations:** ~408k (each winning number in 1st/2nd/3rd/special/consolation)  
- **Date range:** 1985-04-25 → 2026-03-07  
- **Operators:** Magnum 4D, Sports Toto 4D, Da Ma Cai 1+3D  

## Methods

- **Digit uniformity:** For each position (1st–4th digit), chi-square test vs uniform distribution on {0,…,9}.  
- **Number frequency:** Counts per 4D number (0000–9999); summary stats.  
- **Digit correlation:** Pearson correlation between the four digit positions.  
- **Temporal:** Chi-square for uniformity of counts by month and by weekday.  
- **First/last digit:** Same uniformity test for d0 and d3.  
- **By operator:** All of the above (digit uniformity, breakdown, number frequency, first/last digit) are also run **per operator** with operators not mixed (Magnum 4D, Sports Toto 4D, Da Ma Cai 1+3D).  

## Findings

1. **1st and 2nd digit (positions 0 & 1)**  
   - Fail to reject uniformity (p > 0.05).  
   - Consistent with uniform use of digits 0–9 in the first two positions.  

2. **3rd and 4th digit (positions 2 & 3)**  
   - Reject uniformity at α = 0.05 (p ≈ 0.02–0.03).  
   - **Position 2:** Digit 6 is under-represented; 4 and 7 over-represented (vs expected).  
   - **Position 3:** Digit 4 over-represented; 2, 3, 5, 6 under-represented.  
   - Magnitudes are small (deviations in the hundreds on expected ~40k per digit).  

3. **Digit correlations**  
   - Pairwise correlations between d0, d1, d2, d3 are near zero.  
   - No evidence of linear dependence between digit positions.  

4. **Temporal**  
   - By month and by weekday: strongly reject uniformity (p ≈ 0).  
   - Explained by draw calendar (not all days/months have same number of draws), not by digit bias.  

5. **Number frequency**  
   - All 10,000 numbers have appeared at least once.  
   - Counts range from 20 to 78 (mean ≈41).  
   - No single number is excluded; distribution is relatively compact.  

## Interpretation

- The only statistically significant digit-level structure in this dataset is **mild non-uniformity in the 3rd and 4th digits** (positions 2 and 3).  
- Effect sizes are small; the data are largely consistent with **near-uniform** behaviour for the first two digits and **weak structure** in the last two.  
- No evidence of correlation between digit positions or of systematic “lucky” numbers beyond random fluctuation.  

---

## By operator (operators not mixed)

The same analyses are run **per operator** so draws from different operators are not mixed.

- **Sports Toto 4D:** All four digit positions fail to reject uniformity (p > 0.05). Digit distribution consistent with uniform 0–9.
- **Da Ma Cai 1+3D:** Same: all four positions consistent with uniformity.
- **Magnum 4D:** Rejects uniformity at α = 0.05 for **all four** digit positions (p ≈ 0.001–0.04). Position 2: digit 6 strongly under-represented; position 3: digits 0, 2, 3, 5 under-represented and 1, 4, 8 over-represented.

So the **pooled** non-uniformity in positions 2 and 3 is largely driven by **Magnum 4D**. Sports Toto and Da Ma Cai, analyzed separately, do not show significant digit non-uniformity.

For full tables and exact p-values, run `uv run python -m analysis.pattern_analysis`.

---

## Extended and multi-facet analysis (Magnum 4D)

Run: `uv run python -m analysis.pattern_analysis --extended --operator "Magnum 4D"`.

Additional methods and findings:

### Digit sum (0–36)
- Mean ≈ 18.05, std ≈ 5.75 (expected 18, ~5.7 under uniform). No meaningful deviation.

### Benford (first digit 1–9, numbers 1000–9999)
- Strongly reject Benford (Chi² very large, p ≈ 0). 4D draws are designed to be uniform, not natural data, so this is expected.

### Even/odd (count of odd digits per number, 0–4)
- Consistent with binomial(4, 0.5) (Chi² ≈ 6, p ≈ 0.2). No bias.

### Last-two digits (00–99)
- **Reject uniformity** (Chi² ≈ 137.6, p ≈ 0.006).
- Over-represented: **82**, 74, 84, 18, 77.
- Under-represented: **52**, 65, 61, 60, 68.
- Tens digit of last-two: **tens = 6** (i.e. 60–69) is **under** (9.67% vs 10%). Ones digit is close to uniform.

### Within-number digit correlations (adjacent and non-adjacent)
- All near zero (|r| &lt; 0.01). No linear dependence between positions.

### Entropy per position
- All four positions ≈ 3.32 bits (max log₂(10) ≈ 3.32). Near-maximum entropy.

### Double last-two (d2 = d3, e.g. 1200, 3411)
- Share ≈ 0.101 (expected 0.1). Slight over-representation.

### First digit (thousands) 0–9
- **Reject uniformity** (Chi² ≈ 27.8, p ≈ 0.001).
- **Digit 0** and **digit 6** (0xxx and 6xxx) are **under** (9.77%, 9.75%); 7 and 8 (7xxx, 8xxx) slightly over (10.12%, 10.16%). Aligns with digit-6-under and digit-7/8 trends by year.

### Prime (2,3,5,7) and high (5–9) digit counts per number
- Both consistent with binomial (Chi² small, p &gt; 0.8). No structure.

### Digit 6 (pos2) by prize type
- 1st and 3rd: share pos2 = 6 slightly **under** (0.096, 0.093); 2nd and special near 0.1; consolation 0.096. Small differences.

### Autocorrelation (1st prize: draw t vs draw t+1)
- All four positions: r ≈ −0.02 to 0. No predictability from previous draw.

### Other (from ad-hoc runs)
- **Gap** between same 4D number repeating as 1st prize: mean ≈ 2029 draws, median ≈ 1772 (expected ~10000 under uniform). So repeats happen more often than strict uniformity would suggest (fewer draws than 10k).
- **First-two digits (00–99):** Top by count: 58, 57, 98, 85, 89; bottom: 06, 62, 69, 08, 6 — again **6** in first two is under.
- **FFT** of “pos2 = 6” (0/1) over draw order: no strong periodic signal; top magnitudes at short periods (2–5 draws) are noise-level.
- **Month / day-of-week:** pos2 = 6 share varies slightly by month (e.g. Jan–Apr a bit lower) and by weekday (Tue slightly higher); consistent with sampling variation.

### Summary of non–digit-6 patterns
- **Last-two digits:** 00–99 not uniform; tens = 6 under; specific pairs 52, 65, 61, 60, 68 under; 82, 74, 84 over.
- **First digit (thousands):** 0 and 6 under; 7 and 8 over (Chi² significant).
- **Even/odd, prime count, high-digit count:** no structure.
- **No autocorrelation** from previous draw; **no useful periodicity** in pos2 = 6.
- **Gap** between repeats of same number: shorter than 10k (repeats more frequent than naive uniform expectation).

### Golden ratio, Fibonacci, and “special” numbers

- **Fibonacci 4D** (0000, 0001, 0002, 0003, 0005, 0008, 0013, 0021, 0034, 0055, 0089, 0144, 0233, 0377, 0610, 0987, 1597, 2584, 4181, 6765):  
  - Slightly **over**: 4181 (24 vs 15.5), 0000 (21), 0089 (21), 0013 (20), 6765 (19).  
  - Slightly **under**: 0987 (9), 0144 (11), 0610 (12), 0003 (12), 0377 (13).  
  - Under Poisson(λ≈15.5), P(count ≥ 24) ≈ 0.027 and P(count ≤ 9) ≈ 0.056 — borderline; **no strong “golden/Fibonacci” effect** overall.

- **Special numbers** (expected ≈ 15.5 each):  
  - **1618** (golden ratio): 14 (−1.5). **3141** (pi): 4 (−11.5) — notably under. **1414** (√2): 23 (+7.5). **2718** (e): 18 (+2.5). **1234** (sequential): 22 (+6.5). **7777**: 21 (+5.5). **1111**, **8888**, **0618**, **3142** near or slightly under.  
  - Only **3141** is a clear outlier (4 vs 15.5); others are within normal fluctuation.

- **Fibonacci digits** {0,1,2,3,5,8} per number (0–4 count): consistent with binomial(4, 0.6) (Chi² ≈ 2.23, p ≈ 0.69). No “Fibonacci digit” bias.

---

## Position ignored (4 digits as a set)

When the **position of each digit is ignored** and we only consider which 4 digits appear (as a multiset):

### Pattern type (all same, three same, two pairs, one pair, all different)
- **Fail to reject** uniformity (Chi² ≈ 7.85, p ≈ 0.097). Observed proportions match the theoretical (all same 0.1%, three same 3.6%, two pairs 2.7%, one pair 43.2%, all different 50.4%).

### Number of distinct digits (1–4)
- **Fail to reject** (Chi² ≈ 0.09, p ≈ 0.99). Distribution of “how many distinct digits” is as expected.

### All-different multisets (210 combinations of 4 distinct digits)
- **Reject** uniformity (Chi² ≈ 252.4, p ≈ 0.022). So **which set of 4 digits** appears (in any order) is not uniform.
- **Digit frequency in over-represented multisets:** 1, 9, 4, 7, 8, 5, 3, 0, 2; **6** appears **least** (7 times in the over set).
- **Digit frequency in under-represented multisets:** **6** appears **most** (19 times), then 0, 3, 7, 5, …; **4** appears least (8). So **combinations containing 6** tend to be **under**; combinations without 6 (or with 1,4,7,8,9) tend to be **over**, consistent with digit-6-under in Magnum.

### Top over / under multisets (any pattern)
- **Over:** 1347 (+77.5), 5789 (+54.5), 0178 (+53.5), 2358 (+50.5), 1248 (+50.5).
- **Under:** 5679 (−64.5), 0467 (−55.5), 1167 (−52.7), 1678 (−50.5), 1357 (−44.5). Many of the under multisets contain **6** (1678, 1167, 0467, 5679).
