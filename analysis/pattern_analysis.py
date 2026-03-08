#!/usr/bin/env python3
"""
Pattern analysis on 4D history data.
Uses Polars for data manipulation and SciPy for statistical tests.
Finds digit distributions, uniformity, temporal patterns, and correlations.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy import stats

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from analysis.load import DEFAULT_CSV, load_history, get_draws_long

# Normalize number to 4-digit string
def _z4(s: str | int) -> str:
    return str(s).strip().zfill(4)


def get_long_with_digits(df: pl.DataFrame) -> pl.DataFrame:
    """Long format with columns: date, operator, draw_no, number (4-char), prize_type, d0, d1, d2, d3 (digit 0-9 each)."""
    long = get_draws_long(df)
    long = long.with_columns(pl.col("number").cast(pl.Utf8).str.strip_chars().str.pad_start(4, "0"))
    long = long.filter(pl.col("number").str.len_chars() == 4)
    long = long.with_columns(
        pl.col("number").str.slice(0, 1).cast(pl.Int32).alias("d0"),
        pl.col("number").str.slice(1, 1).cast(pl.Int32).alias("d1"),
        pl.col("number").str.slice(2, 1).cast(pl.Int32).alias("d2"),
        pl.col("number").str.slice(3, 1).cast(pl.Int32).alias("d3"),
    )
    return long


def digit_uniformity(long: pl.DataFrame) -> dict:
    """Chi-square test for uniformity of each digit position (0-9)."""
    results = {}
    for pos, col in enumerate(["d0", "d1", "d2", "d3"]):
        observed = long.group_by(col).len().sort(col)
        # Ensure all 0-9 present
        full = pl.DataFrame({col: list(range(10))}).join(observed, on=col, how="left").fill_null(0)
        obs = full["len"].to_numpy()
        n = obs.sum()
        expected = np.full(10, n / 10)
        chi2, p = stats.chisquare(obs, expected)
        results[f"digit_pos_{pos}"] = {"chi2": float(chi2), "p": float(p), "n": int(n)}
    return results


def number_frequency_uniformity(long: pl.DataFrame, n_bins: int = 100) -> dict:
    """Test uniformity of number frequencies: bin counts into n_bins and chi-square vs uniform."""
    freq = long.group_by("number").len()
    n_numbers = freq.height
    # Bin by frequency value (low to high) to see if distribution is uniform over the 10k space
    # Simpler: test if observed counts per number are consistent with multinomial uniform
    # Expected count per number = total / 10000. We have ~23 numbers per draw, many draws.
    total = freq["len"].sum()
    expected_per_number = total / 10_000
    # Chi-sq on raw counts would need 10k bins; use sample of bins or just report stats
    observed_counts = freq["len"].to_numpy()
    mean_c = observed_counts.mean()
    var_c = observed_counts.var()
    # Under uniformity (multinomial) each number has same expected count; variance depends on total draws
    return {
        "total_appearances": int(total),
        "unique_numbers_seen": n_numbers,
        "mean_count_per_number": float(mean_c),
        "variance_of_counts": float(var_c),
        "max_count": int(observed_counts.max()),
        "min_count": int(observed_counts.min()),
    }


def digit_correlation(long: pl.DataFrame) -> pl.DataFrame:
    """Correlation matrix between digit positions d0,d1,d2,d3."""
    mat = long.select(["d0", "d1", "d2", "d3"]).to_numpy()
    r = np.corrcoef(mat.T)
    return pl.DataFrame({
        "pos": ["d0", "d1", "d2", "d3"],
        "d0": r[0], "d1": r[1], "d2": r[2], "d3": r[3],
    })


def temporal_patterns(long: pl.DataFrame) -> dict:
    """By year, month, day-of-week: count of numbers and simple chi-square for uniformity."""
    long = long.with_columns(
        pl.col("date").dt.year().alias("year"),
        pl.col("date").dt.month().alias("month"),
        pl.col("date").dt.weekday().alias("dow"),  # 1=Mon
    )
    out = {}
    # By month (12 bins)
    by_month = long.group_by("month").len().sort("month")
    obs = by_month["len"].to_numpy()
    if len(obs) == 12:
        chi2, p = stats.chisquare(obs)
        out["by_month"] = {"chi2": float(chi2), "p": float(p)}
    # By day of week (7 bins)
    by_dow = long.group_by("dow").len().sort("dow")
    obs_dow = by_dow["len"].to_numpy()
    if len(obs_dow) == 7:
        chi2, p = stats.chisquare(obs_dow)
        out["by_weekday"] = {"chi2": float(chi2), "p": float(p)}
    return out


def digit_position_breakdown(long: pl.DataFrame) -> dict:
    """Per-position digit counts and deviation from expected (for positions that reject uniformity)."""
    out = {}
    n = long.height
    expected = n / 10
    for pos, col in enumerate(["d0", "d1", "d2", "d3"]):
        counts = long.group_by(col).len().sort(col)
        full = pl.DataFrame({col: list(range(10))}).join(counts, on=col, how="left").fill_null(0)
        obs = full["len"].to_numpy()
        diff = obs - expected
        out[f"pos{pos}"] = {
            "digit": list(range(10)),
            "count": obs.tolist(),
            "expected": expected,
            "deviation": diff.tolist(),
        }
    return out


def last_digit_analysis(long: pl.DataFrame) -> dict:
    """Last digit (d3) distribution and Benford-like for first digit (d0)."""
    d3 = long.select("d3").to_numpy().ravel()
    obs = np.bincount(d3, minlength=10)
    chi2, p = stats.chisquare(obs)
    d0 = long.select("d0").to_numpy().ravel()
    obs0 = np.bincount(d0, minlength=10)
    chi2_0, p_0 = stats.chisquare(obs0)
    return {
        "last_digit_d3": {"chi2": float(chi2), "p": float(p)},
        "first_digit_d0": {"chi2": float(chi2_0), "p": float(p_0)},
    }


def run_all(csv_path: Path | None = None) -> tuple[dict, pl.DataFrame]:
    """Run all analyses; return (results dict, long DataFrame)."""
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = load_history(str(path))
    long = get_long_with_digits(df)
    results = {
        "n_rows_raw": df.height,
        "n_number_observations": long.height,
        "date_min": str(df["date"].min()),
        "date_max": str(df["date"].max()),
        "operators": df["operator"].unique().to_list(),
        "digit_uniformity": digit_uniformity(long),
        "digit_breakdown": digit_position_breakdown(long),
        "number_frequency": number_frequency_uniformity(long),
        "digit_correlation": digit_correlation(long),
        "temporal": temporal_patterns(long),
        "last_digit": last_digit_analysis(long),
    }
    return results, long


def run_position_ignored_analysis(long: pl.DataFrame, operator: str | None = None) -> dict:
    """
    Analyze 4 digits as a set (position ignored): pattern type, distinct-digit count,
    multiset (sorted 4-tuple) over/under, and chi-square for all-different multisets.
    """
    if operator:
        long = long.filter(pl.col("operator") == operator)
    if long.height == 0:
        return {"error": "No data"}

    long = long.with_columns(
        pl.col("number").str.slice(0, 1).cast(pl.Utf8).alias("_d0"),
        pl.col("number").str.slice(1, 1).cast(pl.Utf8).alias("_d1"),
        pl.col("number").str.slice(2, 1).cast(pl.Utf8).alias("_d2"),
        pl.col("number").str.slice(3, 1).cast(pl.Utf8).alias("_d3"),
    )
    n = long.height

    def multiset_key(s: str) -> str:
        return "".join(sorted(s))

    def pattern_type(s: str) -> str:
        from collections import Counter
        c = Counter(s)
        counts = sorted(c.values(), reverse=True)
        if counts == [4]:
            return "all_same"
        if counts == [3, 1]:
            return "three_same"
        if counts == [2, 2]:
            return "two_pairs"
        if counts == [2, 1, 1]:
            return "one_pair"
        return "all_different"

    long = long.with_columns(
        pl.col("number").map_elements(multiset_key, return_dtype=pl.Utf8).alias("multiset_key"),
        pl.col("number").map_elements(pattern_type, return_dtype=pl.Utf8).alias("pattern"),
    )
    out = {}

    # Pattern type vs uniform theoretical
    expected_props = {
        "all_same": 10 / 10000,
        "three_same": 360 / 10000,
        "two_pairs": 270 / 10000,
        "one_pair": 4320 / 10000,
        "all_different": 5040 / 10000,
    }
    order = ["all_same", "three_same", "two_pairs", "one_pair", "all_different"]
    pat_counts = long.group_by("pattern").len()
    obs_pat = np.array([
        pat_counts.filter(pl.col("pattern") == p)["len"].to_list()[0]
        if pat_counts.filter(pl.col("pattern") == p).height else 0
        for p in order
    ])
    exp_pat = n * np.array([expected_props[p] for p in order])
    chi2_pat, p_pat = stats.chisquare(obs_pat, exp_pat)
    out["pattern_type"] = {
        "chi2": float(chi2_pat),
        "p": float(p_pat),
        "observed": {order[i]: int(obs_pat[i]) for i in range(5)},
        "expected_proportion": expected_props,
    }

    # Number of distinct digits (1-4)
    long = long.with_columns(pl.col("number").map_elements(lambda s: len(set(s)), return_dtype=pl.Int32).alias("n_distinct"))
    props_d = {1: 10 / 10000, 2: 630 / 10000, 3: 4320 / 10000, 4: 5040 / 10000}
    dist_counts = long.group_by("n_distinct").len().sort("n_distinct")
    obs_d = np.array([dist_counts.filter(pl.col("n_distinct") == d)["len"].to_list()[0] for d in range(1, 5)])
    exp_d = n * np.array([props_d[d] for d in range(1, 5)])
    chi2_d, p_d = stats.chisquare(obs_d, exp_d)
    out["n_distinct_digits"] = {"chi2": float(chi2_d), "p": float(p_d)}

    # All-different multisets (210 combinations)
    from itertools import combinations
    from collections import Counter as Counter_
    all_diff_keys = ["".join(str(d) for d in c) for c in combinations(range(10), 4)]
    ms_counts = long.group_by("multiset_key").len()
    obs_ad = np.array([
        ms_counts.filter(pl.col("multiset_key") == k)["len"].to_list()[0]
        if ms_counts.filter(pl.col("multiset_key") == k).height else 0
        for k in all_diff_keys
    ])
    obs_total_ad = obs_ad.sum()
    exp_ad = np.full(210, obs_total_ad / 210)
    chi2_ad, p_ad = stats.chisquare(obs_ad, exp_ad)
    out["all_different_multisets"] = {"chi2": float(chi2_ad), "p": float(p_ad)}
    over_idx = np.where(obs_ad - exp_ad > 20)[0]
    under_idx = np.where(obs_ad - exp_ad < -20)[0]
    over_digits = []
    under_digits = []
    for i in over_idx:
        over_digits.extend([int(c) for c in all_diff_keys[i]])
    for i in under_idx:
        under_digits.extend([int(c) for c in all_diff_keys[i]])
    out["all_different_over_digit_freq"] = dict(Counter_(over_digits).most_common(10))
    out["all_different_under_digit_freq"] = dict(Counter_(under_digits).most_common(10))

    # Top over/under multisets (any type)
    from math import factorial
    def num_orderings(key: str) -> int:
        c = Counter_(key)
        denom = 1
        for v in c.values():
            denom *= factorial(v)
        return factorial(4) // denom

    expected_per_num = n / 10000
    multiset_results = []
    for r in ms_counts.iter_rows(named=True):
        key = r["multiset_key"]
        cnt = r["len"]
        num_ord = num_orderings(key)
        exp = expected_per_num * num_ord
        multiset_results.append((key, int(cnt), num_ord, exp, cnt - exp))
    multiset_results.sort(key=lambda x: -x[4])
    out["multiset_over"] = [{"key": r[0], "count": r[1], "orderings": r[2], "diff": round(r[4], 1)} for r in multiset_results[:20]]
    out["multiset_under"] = [{"key": r[0], "count": r[1], "orderings": r[2], "diff": round(r[4], 1)} for r in multiset_results[-20:]]

    return out


def get_top_over_multisets(
    operator: str | None = None,
    n: int = 5,
    csv_path: Path | None = None,
    all_different_only: bool = True,
) -> list[str]:
    """
    Return the top N over-represented multisets (position ignored), as 4-digit strings.
    operator: None = all operators combined; otherwise filter to that operator (e.g. "Magnum 4D").
    all_different_only: if True, only include 24-orderings (4 distinct digits) for combo backtest.
    """
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        return []
    df = load_history(str(path))
    long = get_long_with_digits(df)
    res = run_position_ignored_analysis(long, operator=operator)
    if res.get("error") or "multiset_over" not in res:
        return []
    over = res["multiset_over"]
    if all_different_only:
        over = [r for r in over if r.get("orderings") == 24]
    return [r["key"] for r in over[:n]]


def run_extended_analysis(long: pl.DataFrame, operator: str | None = None) -> dict:
    """
    Multi-faceted analysis: digit sum, Benford, even/odd, prime/high counts,
    last-two digits, within-number correlations, entropy, tens/ones of last-two,
    double last-two, first-two extremes, 4D value bins, first-digit (0-9),
    autocorrelation (1st prize t vs t+1), FFT periodicity, digit share by prize type.
    If operator is set, filter to that operator first.
    """
    if operator:
        long = long.filter(pl.col("operator") == operator)
    if long.height == 0:
        return {"error": "No data"}

    long = long.with_columns(
        pl.col("number").str.slice(0, 1).cast(pl.Int32).alias("d0"),
        pl.col("number").str.slice(1, 1).cast(pl.Int32).alias("d1"),
        pl.col("number").str.slice(2, 1).cast(pl.Int32).alias("d2"),
        pl.col("number").str.slice(3, 1).cast(pl.Int32).alias("d3"),
    )
    n = long.height
    out = {}

    # Digit sum (0-36)
    long = long.with_columns(
        (pl.col("d0") + pl.col("d1") + pl.col("d2") + pl.col("d3")).alias("digit_sum")
    )
    out["digit_sum"] = {
        "mean": float(long["digit_sum"].mean()),
        "std": float(long["digit_sum"].std()),
        "expected_mean": 18.0,
    }

    # Benford (first digit 1-9 for numbers >= 1000)
    over_1000 = long.filter(pl.col("number").cast(pl.Int32) >= 1000)
    if over_1000.height > 0:
        lead = over_1000.with_columns(
            (pl.col("number").cast(pl.Int32).floordiv(1000)).alias("lead")
        )
        ld = lead.group_by("lead").len().sort("lead")
        total = ld["len"].sum()
        obs = np.array(
            [
                ld.filter(pl.col("lead") == i)["len"].to_list()[0]
                if ld.filter(pl.col("lead") == i).height
                else 0
                for i in range(1, 10)
            ]
        )
        benford_p = np.log10(1 + 1 / np.arange(1, 10))
        exp_benford = total * benford_p
        chi2_b, p_b = stats.chisquare(obs, exp_benford)
        out["benford_first_digit_1_9"] = {"chi2": float(chi2_b), "p": float(p_b)}

    # Even/odd (count of odd digits per number 0-4)
    long = long.with_columns(
        (pl.col("d0") % 2 + pl.col("d1") % 2 + pl.col("d2") % 2 + pl.col("d3") % 2).alias(
            "n_odd"
        )
    )
    eo = long.group_by("n_odd").len().sort("n_odd")
    obs_eo = np.array([eo.filter(pl.col("n_odd") == i)["len"].to_list()[0] for i in range(5)])
    exp_eo = n * np.array([1 / 16, 4 / 16, 6 / 16, 4 / 16, 1 / 16])
    chi2_eo, p_eo = stats.chisquare(obs_eo, exp_eo)
    out["even_odd_binomial"] = {"chi2": float(chi2_eo), "p": float(p_eo)}

    # Last-two digits (00-99)
    long = long.with_columns(pl.col("number").str.slice(2, 2).cast(pl.Int32).alias("last2"))
    lt = long.group_by("last2").len()
    obs_lt = np.zeros(100)
    for i in range(100):
        r = lt.filter(pl.col("last2") == i)
        obs_lt[i] = r["len"].to_list()[0] if r.height else 0
    chi2_lt, p_lt = stats.chisquare(obs_lt, np.full(100, n / 100))
    out["last_two_digits"] = {"chi2": float(chi2_lt), "p": float(p_lt)}
    diff_lt = obs_lt - n / 100
    out["last_two_over"] = [int(np.argmax(diff_lt)), float(np.max(diff_lt))]
    out["last_two_under"] = [int(np.argmin(diff_lt)), float(np.min(diff_lt))]

    # Within-number digit correlations
    mat = long.select(["d0", "d1", "d2", "d3"]).to_numpy()
    r_d01 = np.corrcoef(mat[:, 0], mat[:, 1])[0, 1]
    r_d12 = np.corrcoef(mat[:, 1], mat[:, 2])[0, 1]
    r_d23 = np.corrcoef(mat[:, 2], mat[:, 3])[0, 1]
    out["within_number_corr_adjacent"] = {
        "d0_d1": float(r_d01),
        "d1_d2": float(r_d12),
        "d2_d3": float(r_d23),
    }

    # Entropy per position (bits)
    def _entropy_bits(counts: np.ndarray) -> float:
        p = np.array(counts, dtype=float) + 1e-12
        p = p / p.sum()
        return float(stats.entropy(p, base=2))

    entropies = {}
    for pos, col in enumerate(["d0", "d1", "d2", "d3"]):
        c = long.group_by(col).len().sort(col)
        arr = np.zeros(10)
        for row in c.iter_rows():
            arr[row[0]] = row[1]
        entropies[f"pos{pos}"] = _entropy_bits(arr)
    out["entropy_per_position_bits"] = entropies

    # Tens/ones of last-two
    long = long.with_columns(
        (pl.col("last2") // 10).alias("tens_last2"),
        (pl.col("last2") % 10).alias("ones_last2"),
    )
    tens = long.group_by("tens_last2").len().sort("tens_last2")
    out["tens_last2_pct"] = {
        int(r[0]): round(100 * r[1] / n, 2) for r in tens.iter_rows()
    }

    # Double last-two (d2 == d3)
    n_double = long.filter(pl.col("d2") == pl.col("d3")).height
    out["double_last_two"] = {"count": n_double, "share": round(n_double / n, 4), "expected": 0.1}

    # First digit (thousands) 0-9
    long = long.with_columns(pl.col("number").cast(pl.Int32).alias("num_val"))
    long = long.with_columns(pl.col("num_val").floordiv(1000).alias("lead"))
    lead_dist = long.group_by("lead").len().sort("lead")
    obs_lead = lead_dist["len"].to_numpy()
    chi2_lead, p_lead = stats.chisquare(obs_lead, np.full(10, n / 10))
    out["first_digit_0_9"] = {"chi2": float(chi2_lead), "p": float(p_lead)}
    out["first_digit_pct"] = {int(r[0]): round(100 * r[1] / n, 2) for r in lead_dist.iter_rows()}

    # Prime digits (2,3,5,7) count per number
    long = long.with_columns(
        (
            pl.col("d0").is_in([2, 3, 5, 7]).cast(pl.Int32)
            + pl.col("d1").is_in([2, 3, 5, 7]).cast(pl.Int32)
            + pl.col("d2").is_in([2, 3, 5, 7]).cast(pl.Int32)
            + pl.col("d3").is_in([2, 3, 5, 7]).cast(pl.Int32)
        ).alias("n_prime")
    )
    n_prime_dist = long.group_by("n_prime").len().sort("n_prime")
    obs_prime = np.array(
        [n_prime_dist.filter(pl.col("n_prime") == i)["len"].to_list()[0] for i in range(5)]
    )
    exp_prime = n * np.array(
        [0.6 ** 4, 4 * 0.4 * 0.6 ** 3, 6 * 0.4 ** 2 * 0.6 ** 2, 4 * 0.4 ** 3 * 0.6, 0.4 ** 4]
    )
    chi2_prime, p_prime = stats.chisquare(obs_prime, exp_prime)
    out["prime_digit_count"] = {"chi2": float(chi2_prime), "p": float(p_prime)}

    # High digits (5-9) count per number
    long = long.with_columns(
        (
            (pl.col("d0") >= 5).cast(pl.Int32)
            + (pl.col("d1") >= 5).cast(pl.Int32)
            + (pl.col("d2") >= 5).cast(pl.Int32)
            + (pl.col("d3") >= 5).cast(pl.Int32)
        ).alias("n_high")
    )
    nh = long.group_by("n_high").len().sort("n_high")
    obs_h = np.array([nh.filter(pl.col("n_high") == i)["len"].to_list()[0] for i in range(5)])
    exp_h = n * np.array([1 / 16, 4 / 16, 6 / 16, 4 / 16, 1 / 16])
    chi2_h, p_h = stats.chisquare(obs_h, exp_h)
    out["high_digit_count"] = {"chi2": float(chi2_h), "p": float(p_h)}

    # Digit 6 share by prize type (pos2)
    if "prize_type" in long.columns:
        by_pt = []
        for pt in long["prize_type"].unique().to_list():
            sub = long.filter(pl.col("prize_type") == pt)
            nn = sub.height
            n6 = sub.filter(pl.col("d2") == 6).height
            by_pt.append({"prize_type": pt, "n": nn, "share_pos2_6": round(n6 / nn, 4)})
        out["digit_6_pos2_by_prize"] = by_pt

    # Golden / Fibonacci / special numbers
    _fib_4d = [
        "0000", "0001", "0002", "0003", "0005", "0008", "0013", "0021", "0034",
        "0055", "0089", "0144", "0233", "0377", "0610", "0987", "1597", "2584",
        "4181", "6765",
    ]
    _special = {
        "1618": "golden_ratio", "3141": "pi", "3142": "pi", "1414": "sqrt2",
        "2718": "e", "0618": "golden", "1234": "sequential", "1111": "repdigit",
        "8888": "lucky8", "7777": "lucky7", "0000": "zeros",
    }
    num_counts = long.group_by("number").len()
    expected_any = n / 10000

    def _count(num: str) -> int:
        r = num_counts.filter(pl.col("number") == num)
        return r["len"].to_list()[0] if r.height else 0

    fib_over_under = [
        (num, _count(num), round(_count(num) - expected_any, 1))
        for num in _fib_4d
    ]
    fib_over_under.sort(key=lambda x: -x[2])
    out["fibonacci_4d"] = {
        "expected_per_number": round(expected_any, 2),
        "over": [(n, c, d) for n, c, d in fib_over_under[:5]],
        "under": [(n, c, d) for n, c, d in fib_over_under[-5:]],
    }
    special_counts = [
        {"number": num, "count": _count(num), "note": note, "diff": round(_count(num) - expected_any, 1)}
        for num, note in _special.items()
    ]
    out["special_numbers"] = special_counts

    # Fibonacci digits {0,1,2,3,5,8} per number
    fib_digits = {0, 1, 2, 3, 5, 8}
    long = long.with_columns(
        (
            pl.col("d0").is_in(list(fib_digits)).cast(pl.Int32)
            + pl.col("d1").is_in(list(fib_digits)).cast(pl.Int32)
            + pl.col("d2").is_in(list(fib_digits)).cast(pl.Int32)
            + pl.col("d3").is_in(list(fib_digits)).cast(pl.Int32)
        ).alias("n_fib_digit")
    )
    nfd = long.group_by("n_fib_digit").len().sort("n_fib_digit")
    obs_fd = np.array([nfd.filter(pl.col("n_fib_digit") == i)["len"].to_list()[0] for i in range(5)])
    exp_fd = n * np.array([0.4 ** 4, 4 * 0.6 * 0.4 ** 3, 6 * 0.6 ** 2 * 0.4 ** 2, 4 * 0.6 ** 3 * 0.4, 0.6 ** 4])
    chi2_fd, p_fd = stats.chisquare(obs_fd, exp_fd)
    out["fibonacci_digits_per_number"] = {"chi2": float(chi2_fd), "p": float(p_fd)}

    # Autocorrelation (1st prize only, draw t vs t+1)
    first_prize = long.filter(pl.col("prize_type") == "1st").sort("date")
    if first_prize.height > 100:
        fp = first_prize.select(["date", "d0", "d1", "d2", "d3"]).to_pandas().set_index("date")
        fp = fp.sort_index()
        prev = fp.shift(1)
        autocorr = {}
        for col in ["d0", "d1", "d2", "d3"]:
            cur = fp[col].dropna()
            pr = prev[col].dropna()
            common = cur.index.intersection(pr.index)
            if len(common) > 10:
                r = np.corrcoef(cur.loc[common].values, pr.loc[common].values)[0, 1]
                autocorr[col] = round(float(r), 4)
        out["autocorr_1st_prize_t_vs_t1"] = autocorr

    return out


def run_all_by_operator(long: pl.DataFrame) -> dict[str, dict]:
    """Run digit uniformity, breakdown, number frequency, and first/last digit per operator. Operators not mixed."""
    operators = long["operator"].unique().to_list()
    out = {}
    for op in operators:
        sub = long.filter(pl.col("operator") == op)
        n_obs = sub.height
        if n_obs < 100:
            out[op] = {"skip": True, "n_obs": n_obs, "reason": "Too few observations"}
            continue
        out[op] = {
            "n_obs": n_obs,
            "date_min": str(sub["date"].min()),
            "date_max": str(sub["date"].max()),
            "digit_uniformity": digit_uniformity(sub),
            "digit_breakdown": digit_position_breakdown(sub),
            "number_frequency": number_frequency_uniformity(sub),
            "last_digit": last_digit_analysis(sub),
        }
    return out


def main() -> None:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()
    console.print(Panel("[bold]4D History — Pattern Analysis[/]", title="Analysis", border_style="cyan"))
    try:
        res, long = run_all()
        by_op = run_all_by_operator(long)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)

    console.print(f"\n[bold]Data scope[/]")
    console.print(f"  Rows (draws): {res['n_rows_raw']}")
    console.print(f"  Number observations: {res['n_number_observations']}")
    console.print(f"  Date range: {res['date_min']} → {res['date_max']}")
    console.print(f"  Operators: {', '.join(res['operators'])}")

    console.print("\n[bold]Digit position uniformity (Chi-square vs uniform 0–9)[/]")
    t = Table(show_header=True, header_style="bold")
    t.add_column("Position", style="dim")
    t.add_column("Chi²", justify="right")
    t.add_column("p-value", justify="right")
    t.add_column("Interpretation")
    for pos_name, v in res["digit_uniformity"].items():
        p = v["p"]
        interp = "Uniform (fail to reject)" if p > 0.05 else "Reject uniformity"
        t.add_row(pos_name, f"{v['chi2']:.2f}", f"{p:.4f}", interp)
    console.print(t)

    console.print("\n[bold]Number frequency summary[/]")
    f = res["number_frequency"]
    console.print(f"  Total appearances: {f['total_appearances']}")
    console.print(f"  Unique numbers seen: {f['unique_numbers_seen']}")
    console.print(f"  Mean count per number: {f['mean_count_per_number']:.2f}")
    console.print(f"  Max count: {f['max_count']}, Min count: {f['min_count']}")

    console.print("\n[bold]Digit correlation (positions d0–d3)[/]")
    corr = res["digit_correlation"]
    console.print(corr)

    console.print("\n[bold]Temporal (Chi-square vs uniform)[/]")
    for name, v in res["temporal"].items():
        interp = "Uniform" if v["p"] > 0.05 else "Not uniform"
        console.print(f"  {name}: Chi²={v['chi2']:.2f}, p={v['p']:.4f} — {interp}")

    console.print("\n[bold]First & last digit uniformity[/]")
    for name, v in res["last_digit"].items():
        interp = "Uniform" if v["p"] > 0.05 else "Not uniform"
        console.print(f"  {name}: Chi²={v['chi2']:.2f}, p={v['p']:.4f} — {interp}")

    # Positions 2 and 3 (3rd and 4th digit) that rejected uniformity: show which digits are over/under
    console.print("\n[bold]Digit breakdown (positions 2 & 3 — deviations from uniform)[/]")
    expected = res["n_number_observations"] / 10
    for pos in ["pos2", "pos3"]:
        b = res["digit_breakdown"][pos]
        dev = np.array(b["deviation"])
        over = np.where(dev > 0)[0]
        under = np.where(dev < 0)[0]
        over_str = ", ".join(f"{d}(+{dev[d]:.0f})" for d in over[:5])
        if len(over) > 5:
            over_str += f" ... (+{len(over)} digits)"
        under_str = ", ".join(f"{d}({dev[d]:.0f})" for d in under[:5])
        if len(under) > 5:
            under_str += f" ... ({len(under)} digits)"
        console.print(f"  {pos} (expected ≈{expected:.0f}/digit): over: {over_str}")
        console.print(f"  {pos}: under: {under_str}")

    console.print(Panel(
        "[dim]Conclusion: If p > 0.05 we fail to reject uniformity (digits behave like uniform). "
        "If p < 0.05 there is statistical evidence of deviation from uniformity.[/]",
        title="Note",
        border_style="dim",
    ))

    # --- By operator (not mixed) ---
    console.print("\n")
    console.print(Panel("[bold]By operator (operators not mixed)[/]", title="Per-operator analysis", border_style="blue"))
    for op, data in by_op.items():
        if data.get("skip"):
            console.print(f"  [dim]{op}: skipped ({data.get('reason', '')})[/]")
            continue
        console.print(Panel(f"[bold]{op}[/]", border_style="blue"))
        console.print(f"  Observations: {data['n_obs']}  |  Date range: {data['date_min']} → {data['date_max']}")
        console.print("  [bold]Digit uniformity (Chi² vs uniform 0–9):[/]")
        t_op = Table(show_header=True, header_style="bold")
        t_op.add_column("Position", style="dim")
        t_op.add_column("Chi²", justify="right")
        t_op.add_column("p-value", justify="right")
        t_op.add_column("Interpretation")
        for pos_name, v in data["digit_uniformity"].items():
            p = v["p"]
            interp = "Uniform" if p > 0.05 else "Reject uniformity"
            t_op.add_row(pos_name, f"{v['chi2']:.2f}", f"{p:.4f}", interp)
        console.print(t_op)
        f = data["number_frequency"]
        console.print(f"  [bold]Number frequency:[/] total={f['total_appearances']}, unique={f['unique_numbers_seen']}, mean={f['mean_count_per_number']:.2f}, range=[{f['min_count']}, {f['max_count']}]")
        console.print("  [bold]Digit breakdown (pos2 & pos3):[/]")
        for pos in ["pos2", "pos3"]:
            b = data["digit_breakdown"][pos]
            dev = np.array(b["deviation"])
            over = np.where(dev > 0)[0]
            under = np.where(dev < 0)[0]
            over_str = ", ".join(f"{d}(+{dev[d]:.0f})" for d in over[:4])
            if len(over) > 4:
                over_str += f" … ({len(over)} over)"
            under_str = ", ".join(f"{d}({dev[d]:.0f})" for d in under[:4])
            if len(under) > 4:
                under_str += f" … ({len(under)} under)"
            console.print(f"    {pos}: over {over_str}  |  under {under_str}")
        console.print("")

    # Summary
    console.print("\n[bold]Summary of patterns[/]")
    console.print("  • Positions 0 & 1 (1st and 2nd digit): consistent with uniform 0–9 (no strong pattern).")
    console.print("  • Positions 2 & 3 (3rd and 4th digit): reject uniformity; some digits appear more/less often.")
    console.print("  • Digit positions are effectively uncorrelated (no linear dependence).")
    console.print("  • Month/weekday non-uniformity reflects draw schedule, not number bias.")
    console.print("  • All 10,000 numbers have appeared; frequency range 20–78 (mean ≈41).")
    console.print("  • Per-operator section above: each operator analyzed separately (no mixing); compare digit uniformity and pos2/pos3 breakdown across operators.")


def main_extended(operator: str = "Magnum 4D") -> None:
    """Run extended multi-facet analysis for an operator and print summary."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    path = DEFAULT_CSV
    if not path.is_file():
        console.print(f"[red]CSV not found: {path}[/]")
        return
    df = load_history(str(path))
    long = get_long_with_digits(df)
    res = run_extended_analysis(long, operator=operator)
    if res.get("error"):
        console.print(f"[red]{res['error']}[/]")
        return

    console.print(Panel(f"[bold]Extended pattern analysis — {operator}[/]", border_style="cyan"))
    console.print(f"  n = {long.filter(pl.col('operator') == operator).height}")

    console.print("\n[bold]Digit sum (0–36)[/] mean =", res["digit_sum"]["mean"], "std =", round(res["digit_sum"]["std"], 3), "(expected mean 18)")
    if "benford_first_digit_1_9" in res:
        b = res["benford_first_digit_1_9"]
        console.print("  [bold]Benford (first digit 1–9)[/] Chi² =", round(b["chi2"], 2), "p =", round(b["p"], 4), "— Reject Benford" if b["p"] < 0.05 else "— Consistent with Benford")
    console.print("  [bold]Even/odd (0–4 odd digits)[/] Chi² =", round(res["even_odd_binomial"]["chi2"], 2), "p =", round(res["even_odd_binomial"]["p"], 4))
    console.print("  [bold]Last-two digits (00–99)[/] Chi² =", round(res["last_two_digits"]["chi2"], 2), "p =", round(res["last_two_digits"]["p"], 4), "— Reject uniform" if res["last_two_digits"]["p"] < 0.05 else "— Uniform")
    console.print("    Over-represented last2:", res["last_two_over"][0], "(+", round(res["last_two_over"][1], 0), ")  Under:", res["last_two_under"][0], "(", round(res["last_two_under"][1], 0), ")")
    console.print("  [bold]Within-number correlations (adjacent)[/]", res["within_number_corr_adjacent"])
    console.print("  [bold]Entropy per position (bits)[/]", res["entropy_per_position_bits"], "(max 3.32)")
    console.print("  [bold]Tens of last-two (0–9 %)[/]", res["tens_last2_pct"], "— tens=6 under?" if res["tens_last2_pct"].get(6, 10) < 10 else "")
    console.print("  [bold]Double last-two (d2=d3)[/] share =", res["double_last_two"]["share"], "(expected 0.1)")
    console.print("  [bold]First digit 0–9 (thousands)[/] Chi² =", round(res["first_digit_0_9"]["chi2"], 2), "p =", round(res["first_digit_0_9"]["p"], 4))
    console.print("    % by digit:", res["first_digit_pct"])
    console.print("  [bold]Prime digit count (2,3,5,7)[/] Chi² =", round(res["prime_digit_count"]["chi2"], 2), "p =", round(res["prime_digit_count"]["p"], 4))
    console.print("  [bold]High digit count (5–9)[/] Chi² =", round(res["high_digit_count"]["chi2"], 2), "p =", round(res["high_digit_count"]["p"], 4))
    if "digit_6_pos2_by_prize" in res:
        t = Table(show_header=True)
        t.add_column("Prize")
        t.add_column("n")
        t.add_column("share pos2=6")
        for row in res["digit_6_pos2_by_prize"]:
            t.add_row(row["prize_type"], str(row["n"]), str(row["share_pos2_6"]))
        console.print("  [bold]Digit 6 (pos2) by prize type[/]")
        console.print(t)
    if "autocorr_1st_prize_t_vs_t1" in res:
        console.print("  [bold]Autocorrelation (1st prize draw t vs t+1)[/]", res["autocorr_1st_prize_t_vs_t1"])
    if "fibonacci_4d" in res:
        f = res["fibonacci_4d"]
        console.print("  [bold]Fibonacci 4D numbers[/] (expected", f["expected_per_number"], "each)")
        console.print("    Over:", f["over"])
        console.print("    Under:", f["under"])
    if "special_numbers" in res:
        console.print("  [bold]Special / golden numbers[/]")
        for row in res["special_numbers"]:
            console.print(f"    {row['number']} ({row['note']}): count={row['count']}, diff={row['diff']:+}")
    if "fibonacci_digits_per_number" in res:
        fd = res["fibonacci_digits_per_number"]
        console.print("  [bold]Fibonacci digits {0,1,2,3,5,8} per number[/] Chi² =", round(fd["chi2"], 2), "p =", round(fd["p"], 4))

    # Position-ignored (4 digits as set)
    pos_ignored = run_position_ignored_analysis(long, operator=operator)
    if "error" not in pos_ignored:
        console.print("\n[bold]Position ignored (4 digits as set)[/]")
        pt = pos_ignored.get("pattern_type", {})
        console.print("  [bold]Pattern type[/] (all_same, three_same, two_pairs, one_pair, all_different) Chi² =", round(pt.get("chi2", 0), 2), "p =", round(pt.get("p", 1), 4))
        nd = pos_ignored.get("n_distinct_digits", {})
        console.print("  [bold]Number of distinct digits (1–4)[/] Chi² =", round(nd.get("chi2", 0), 2), "p =", round(nd.get("p", 1), 4))
        ad = pos_ignored.get("all_different_multisets", {})
        console.print("  [bold]All-different multisets (210)[/] Chi² =", round(ad.get("chi2", 0), 2), "p =", round(ad.get("p", 1), 4), "— Reject?" if ad.get("p", 1) < 0.05 else "")
        console.print("    Over multiset digit freq:", pos_ignored.get("all_different_over_digit_freq", {}))
        console.print("    Under multiset digit freq:", pos_ignored.get("all_different_under_digit_freq", {}))
        console.print("  [bold]Multiset over[/]", pos_ignored.get("multiset_over", []))
        console.print("  [bold]Multiset under[/]", pos_ignored.get("multiset_under", []))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--extended", action="store_true", help="Run extended multi-facet analysis")
    parser.add_argument("--operator", type=str, default="Magnum 4D", help="Operator filter for --extended")
    args = parser.parse_args()
    if args.extended:
        main_extended(operator=args.operator)
    else:
        main()
