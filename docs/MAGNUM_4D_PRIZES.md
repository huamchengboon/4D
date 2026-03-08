# Magnum 4D Prize Structure (Malaysia)

Reference: **standard 4D game**, **per RM1 bet**.  
Source: [4D Naik](https://4dnaik.co/en/blog/magnum-prize-structure), [4DD](https://4dd.co/blog/magnum-prize-structure). Verify on [Magnum 4D official](https://mktuat.magnum4d.my/en) if needed.

---

## Big vs Small (how you buy)

When you buy Magnum 4D you choose **Big** or **Small**:

| Prize category  | Big (RM) | Small (RM) |
|-----------------|----------|-------------|
| 1st             | 2,500    | **3,500**   |
| 2nd             | 1,000    | **2,000**   |
| 3rd             | 500      | **1,000**   |
| Special         | 180      | *Not applicable* |
| Consolation     | 60       | *Not applicable* |

- **Big**: 5 winning categories (1st, 2nd, 3rd, Special, Consolation). More ways to win; lower top prizes.
- **Small**: Only 1st, 2nd, 3rd pay. **Special and Consolation do not pay** on Small. Higher payouts for top 3 only.

---

## Big forecast (5 winning categories, 23 winning numbers per draw)

| Position    | Prize (RM) per RM1 bet | Notes                    |
|------------|------------------------|--------------------------|
| **1st**    | **2,500**              | 1 winning number         |
| **2nd**    | **1,000**              | 1 winning number         |
| **3rd**    | **500**                | 1 winning number         |
| **Special**| **180**                | 10 winning numbers      |
| **Consolation** | **60**             | 10 winning numbers      |

- Total: **1 + 1 + 1 + 10 + 10 = 23** winning numbers per draw.
- Prizes scale with stake (e.g. RM2 bet = double the amounts above).

---

## Small forecast (3 categories only, higher top prizes)

| Position | Prize (RM) per RM1 bet |
|----------|-------------------------|
| **1st**  | **3,500**               |
| **2nd**  | **2,000**               |
| **3rd**  | **1,000**               |

- No Special or Consolation in Small forecast.

---

## 3D (last 3 digits match)

When you bet a **4D number** (e.g. **3567**), you also win if the **last 3 digits** of your number match the last 3 digits of the **1st, 2nd, or 3rd** prize. You get a separate **3D** payout (different from full 4D match).

**Example:** You bet **3567**. Draw result: 1st prize **5567**. Your last 3 digits **567** match 1st’s last 3 digits **567** → you win **3D 1st** (RM 250 for Big, RM 660 for Small). You do **not** need the first digit to match.

### Bet price and 3D payout

- **One stake covers both 4D and 3D.** You choose one bet amount per number (e.g. RM1, RM2, RM5). That same amount is used for both full 4D prizes and 3D (last 3 digits) prizes.
- **All 3D amounts below are per RM1 bet.** If you bet **RM2** on the same number (Big), 3D 1st = 250 × 2 = **RM 500**; 3D 2nd = 210 × 2 = RM 420; 3D 3rd = 150 × 2 = RM 300. Small RM2 → 3D 1st = 660 × 2 = RM 1,320.
- **Minimum stake** is typically RM1 (same as 4D); maximum depends on operator.

| 3D prize (last 3 match) | Big (RM) per RM1 bet | Small (RM) per RM1 bet |
|-------------------------|------------------------|-------------------------|
| Last 3 = 1st prize’s last 3 | **250**  | **660**  |
| Last 3 = 2nd prize’s last 3 | **210**  | *Not applicable* |
| Last 3 = 3rd prize’s last 3 | **150**  | *Not applicable* |

- **Big (ABC)**: 3D 1st, 2nd, 3rd all pay (250, 210, 150) **per RM1**.
- **Small (A)**: Only 3D 1st pays (660 **per RM1**). No 3D 2nd/3rd for Small.

Source: [check4d.org Malaysia prize structure](https://www.check4d.org/malaysia-prize-structure) — “3D (Prize per RM 1 bet)”. Same structure applies to Magnum 4D / 4D Classic.

---

## Summary for analysis

**Big (default in backtests):** 1st 2,500 | 2nd 1,000 | 3rd 500 | Special 180 | Consolation 60.

**Small:** 1st 3,500 | 2nd 2,000 | 3rd 1,000 | Special 0 | Consolation 0. Use `--small` in `backtest_all_numbers` to backtest with Small prizes.

**3D (last 3 digits match 1st/2nd/3rd):** Big — 250 / 210 / 150. Small — 660 for 1st only; no 2nd/3rd.
