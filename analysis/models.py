"""
Baseline "prediction" models for 4D numbers.

Lottery draws are designed to be random and independent. No model can reliably
predict the next draw. These baselines are the only statistically appropriate
options: (1) uniform random, (2) sample by historical frequency.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

import polars as pl

from analysis.load import get_draws_long, get_number_frequencies, load_history

N_NUMBERS = 10_000  # 0000 to 9999


@dataclass
class PredictionResult:
    """Result of evaluating a predictor on holdout draws."""

    model_name: str
    n_holdout_draws: int
    hit_any: int  # predicted set contained actual 1st prize
    hit_rate: float
    expected_random: float  # expected hit rate if random (e.g. 23/10000 for 23 picks)


class BasePredictor(ABC):
    """Abstract base for a 4D number predictor (returns k numbers)."""

    @abstractmethod
    def predict(self, k: int = 23) -> list[str]:
        """Return k 4D numbers (e.g. 23 for one full draw)."""
        ...


class UniformPredictor(BasePredictor):
    """
    Sample uniformly from 0000–9999.
    Statistically appropriate if draws are fair; no historical data used.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def predict(self, k: int = 23) -> list[str]:
        return [f"{self._rng.randint(0, N_NUMBERS - 1):04d}" for _ in range(k)]


class EmpiricalFrequencyPredictor(BasePredictor):
    """
    Sample proportional to historical frequency (with replacement).
    Fits the marginal distribution; does NOT improve prediction of next draw.
    """

    def __init__(self, counts: pl.DataFrame, seed: int | None = None) -> None:
        numbers = counts["number"].to_list()
        weights = counts["count"].to_list()
        total = sum(weights)
        self._probs = [w / total for w in weights]
        self._numbers = numbers
        self._rng = random.Random(seed)

    def predict(self, k: int = 23) -> list[str]:
        return [
            self._rng.choices(self._numbers, weights=self._probs, k=1)[0]
            for _ in range(k)
        ]


class TopKFrequencyPredictor(BasePredictor):
    """
    Always return the top-k most frequently drawn numbers (deterministic).
    No randomness; useful as a naive "hot numbers" baseline.
    """

    def __init__(self, counts: pl.DataFrame, k_max: int = 100) -> None:
        self._top = counts.head(k_max)["number"].to_list()

    def predict(self, k: int = 23) -> list[str]:
        return self._top[:k]


def train_test_split(
    df: pl.DataFrame,
    test_ratio: float = 0.1,
    date_col: str = "date",
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Split by date: latest test_ratio of dates are test."""
    dates = df[date_col].unique().sort(descending=True)
    n_test = max(1, int(len(dates) * test_ratio))
    test_dates = dates.head(n_test)
    train_dates = dates.tail(len(dates) - n_test)
    test_df = df.filter(pl.col(date_col).is_in(test_dates))
    train_df = df.filter(pl.col(date_col).is_in(train_dates))
    return train_df, test_df


def evaluate_predictor(
    predictor: BasePredictor,
    test_long: pl.DataFrame,
    k: int = 23,
    prize_type: str = "1st",
) -> PredictionResult:
    """
    For each test draw, get predictor's k numbers; check if actual 1st prize is in set.
    Returns hit rate (fraction of test draws where predicted set contained the actual).
    """
    test_first = test_long.filter(pl.col("prize_type") == prize_type)
    # One row per (date, operator) for 1st prize
    draws = test_first.unique(subset=["date", "operator"]).select("date", "operator", "number")
    hits = 0
    for row in draws.iter_rows(named=True):
        pred_set = set(predictor.predict(k=k))
        if row["number"] in pred_set:
            hits += 1
    n = draws.height
    hit_rate = hits / n if n else 0.0
    expected_random = k / N_NUMBERS  # P(hit) if uniform
    return PredictionResult(
        model_name=type(predictor).__name__,
        n_holdout_draws=n,
        hit_any=hits,
        hit_rate=hit_rate,
        expected_random=expected_random,
    )


def run_model_comparison(
    csv_path: str | None = None,
    test_ratio: float = 0.1,
    seed: int = 42,
) -> list[PredictionResult]:
    """
    Load data, split train/test, train empirical model on train, evaluate all baselines on test.
    """
    df = load_history(csv_path)
    long_df = get_draws_long(df)
    train_long, test_long = train_test_split(long_df, test_ratio=test_ratio)
    train_dates = train_long["date"].unique()
    freq_train = get_number_frequencies(df.filter(pl.col("date").is_in(train_dates)))

    predictors = [
        UniformPredictor(seed=seed),
        EmpiricalFrequencyPredictor(freq_train, seed=seed),
        TopKFrequencyPredictor(freq_train, k_max=100),
    ]

    results = []
    for p in predictors:
        r = evaluate_predictor(p, test_long, k=23)
        results.append(r)
    return results
