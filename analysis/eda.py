"""
Exploratory data analysis and statistical tests for 4D draw data.
Tests for uniformity, independence, and digit distribution.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl
from scipy import stats

from analysis.load import get_draws_long, load_history

# All 4D numbers 0000-9999
N_NUMBERS = 10_000


@dataclass
class EDAResult:
    """Summary of EDA and statistical tests."""

    n_draws: int
    n_number_records: int
    date_min: str
    date_max: str
    chi2_uniform: float
    chi2_pvalue: float
    is_uniform: bool  # True if we cannot reject uniformity at alpha=0.05
    first_digit_chi2: float
    first_digit_pvalue: float
    autocorr_lag1: float  # autocorrelation of 1st prize (as int) over time
    conclusion: str


def _get_1st_prize_series(long_df: pl.DataFrame) -> pl.Series:
    """First prize as integer series ordered by date then operator (for autocorrelation)."""
    sub = (
        long_df.filter(pl.col("prize_type") == "1st")
        .select(pl.col("date"), pl.col("operator"), pl.col("number").cast(pl.Int64))
        .unique(subset=["date", "operator"], keep="first")
        .sort(["date", "operator"])
    )
    return sub["number"]


def run_eda(df: pl.DataFrame | None = None, long_df: pl.DataFrame | None = None) -> EDAResult:
    """
    Run full EDA: load data if needed, compute counts, chi-square for uniformity,
    first-digit distribution test, and autocorrelation of 1st prize over time.
    """
    if df is None:
        df = load_history()
    if long_df is None:
        long_df = get_draws_long(df)

    n_draws = df.height
    n_number_records = long_df.height
    date_min = str(df["date"].min())
    date_max = str(df["date"].max())

    # Observed frequency per 4D number (0000-9999); normalize to 4-digit key
    counts = long_df.with_columns(pl.col("number").str.zfill(4).alias("num_4"))
    counts = counts.group_by("num_4").agg(pl.len().alias("count"))
    all_nums = pl.DataFrame({"num": [f"{i:04d}" for i in range(N_NUMBERS)]})
    observed = all_nums.join(
        counts.select(pl.col("num_4").alias("num"), pl.col("count")), on="num", how="left"
    )
    observed = observed.with_columns(pl.col("count").fill_null(0))
    obs = observed["count"].to_numpy().astype(float)
    assert obs.shape[0] == N_NUMBERS, f"expected {N_NUMBERS} bins, got {obs.shape[0]}"
    expected = obs.sum() / N_NUMBERS
    if expected < 1:
        expected = 1.0
    chi2, p_uniform = stats.chisquare(obs, f_exp=[expected] * N_NUMBERS)
    is_uniform = p_uniform >= 0.05

    # First-digit distribution: digits 0-9
    first = long_df.with_columns(pl.col("number").str.slice(0, 1).alias("fd"))
    fd_counts = first.group_by("fd").agg(pl.len().alias("count"))
    full_fd = [0.0] * 10
    for row in fd_counts.iter_rows(named=True):
        d = row["fd"]
        if isinstance(d, str) and d.isdigit():
            full_fd[int(d)] = float(row["count"])
        elif isinstance(d, int) and 0 <= d <= 9:
            full_fd[d] = float(row["count"])
    fd_obs = full_fd
    fd_expected = sum(fd_obs) / 10 or 1.0
    fd_chi2, fd_p = stats.chisquare(fd_obs, f_exp=[fd_expected] * 10)

    # Autocorrelation: 1st prize (one per date per operator) as time series
    first_prizes = _get_1st_prize_series(long_df)
    if first_prizes.len() > 1:
        arr = first_prizes.to_numpy()
        ac = float(stats.pearsonr(arr[:-1], arr[1:])[0])
    else:
        ac = 0.0

    conclusion = (
        "Data is consistent with uniform random draws (no exploitable structure). "
        "Do not use ML for prediction; use uniform or empirical baseline only."
    )
    if not is_uniform:
        conclusion = (
            "Marginal distribution deviates from strict uniformity (chi-square). "
            "Still, draws are typically independent; prediction remains ineffective."
        )

    return EDAResult(
        n_draws=n_draws,
        n_number_records=n_number_records,
        date_min=date_min,
        date_max=date_max,
        chi2_uniform=float(chi2),
        chi2_pvalue=float(p_uniform),
        is_uniform=is_uniform,
        first_digit_chi2=float(fd_chi2),
        first_digit_pvalue=float(fd_p),
        autocorr_lag1=ac,
        conclusion=conclusion,
    )


def print_eda_report(r: EDAResult) -> None:
    """Print human-readable EDA report."""
    print("=" * 60)
    print("4D HISTORY – EXPLORATORY DATA ANALYSIS")
    print("=" * 60)
    print(f"Draw records:     {r.n_draws:,}")
    print(f"Number records:  {r.n_number_records:,}")
    print(f"Date range:      {r.date_min} → {r.date_max}")
    print()
    print("Uniformity (chi-square, 0000–9999):")
    print(f"  χ² = {r.chi2_uniform:.2f}, p = {r.chi2_pvalue:.4f}")
    print(f"  Consistent with uniform? {'Yes' if r.is_uniform else 'No'} (α=0.05)")
    print()
    print("First-digit distribution (0–9):")
    print(f"  χ² = {r.first_digit_chi2:.2f}, p = {r.first_digit_pvalue:.4f}")
    print()
    print("Independence (1st prize lag-1 autocorrelation):")
    print(f"  r = {r.autocorr_lag1:.4f} (≈0 suggests independence)")
    print()
    print("Conclusion:")
    print(f"  {r.conclusion}")
    print("=" * 60)
