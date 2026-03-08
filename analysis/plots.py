"""
Visualization helpers for 4D history.
Uses Seaborn and Matplotlib; accepts Polars DataFrames (converted to pandas for seaborn).
"""

from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl
import seaborn as sns

sns.set_theme(style="whitegrid", palette="husl", font_scale=1.1)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def plot_draws_per_day(
    df: pl.DataFrame,
    save: str | Path | None = None,
    figsize: tuple[float, float] = (10, 4),
) -> None:
    """Number of draw-days over time (draws per calendar day)."""
    pdf = df.to_pandas()
    daily = pdf.groupby("date").size().reset_index(name="draws")
    daily["date"] = daily["date"].astype("datetime64[ns]")

    fig, ax = plt.subplots(figsize=figsize)
    sns.lineplot(data=daily, x="date", y="draws", ax=ax)
    ax.set_title("4D draws per calendar day (Magnum, Da Ma Cai, Sports Toto)")
    ax.set_ylabel("Number of operator-draws")
    plt.xticks(rotation=45)
    plt.tight_layout()
    if save:
        fig.savefig(Path(save), dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


def plot_operator_breakdown(
    df: pl.DataFrame,
    save: str | Path | None = None,
    figsize: tuple[float, float] = (6, 4),
) -> None:
    """Count of records per operator (pie or bar)."""
    pdf = df.to_pandas()
    counts = pdf["operator"].value_counts()

    fig, ax = plt.subplots(figsize=figsize)
    counts.plot(kind="bar", ax=ax, color=sns.color_palette("husl", n_colors=len(counts)))
    ax.set_title("Draws by operator")
    ax.set_ylabel("Count")
    plt.xticks(rotation=15)
    plt.tight_layout()
    if save:
        fig.savefig(Path(save), dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


def plot_number_frequency(
    freq_df: pl.DataFrame,
    top_n: int = 40,
    save: str | Path | None = None,
    figsize: tuple[float, float] = (12, 6),
) -> None:
    """Bar plot of most frequently drawn 4D numbers (top N)."""
    pdf = freq_df.head(top_n).to_pandas()

    fig, ax = plt.subplots(figsize=figsize)
    hue_col = "operator" if "operator" in pdf.columns else None
    sns.barplot(data=pdf, x="number", y="count", hue=hue_col, ax=ax)
    ax.set_title(f"Top {top_n} most frequently drawn 4D numbers")
    ax.set_ylabel("Times drawn")
    plt.xticks(rotation=90)
    plt.tight_layout()
    if save:
        fig.savefig(Path(save), dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


def plot_number_frequency_single(
    freq_df: pl.DataFrame,
    top_n: int = 30,
    save: str | Path | None = None,
    figsize: tuple[float, float] = (12, 5),
) -> None:
    """Bar plot of top N numbers (single series, no operator split)."""
    pdf = freq_df.head(top_n).to_pandas()

    fig, ax = plt.subplots(figsize=figsize)
    sns.barplot(data=pdf, x="number", y="count", color="steelblue", ax=ax)
    ax.set_title(f"Top {top_n} most frequently drawn 4D numbers")
    ax.set_ylabel("Times drawn")
    plt.xticks(rotation=90)
    plt.tight_layout()
    if save:
        fig.savefig(Path(save), dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


def plot_first_digit_distribution(
    long_df: pl.DataFrame,
    save: str | Path | None = None,
    figsize: tuple[float, float] = (8, 4),
) -> None:
    """Distribution of first digit of drawn numbers (1–9, 0)."""
    # First digit: first character of 4D number
    first = long_df.with_columns(pl.col("number").str.slice(0, 1).alias("first_digit"))
    pdf = first.to_pandas()
    digit_counts = pdf["first_digit"].value_counts().sort_index()

    fig, ax = plt.subplots(figsize=figsize)
    digit_counts.plot(kind="bar", ax=ax, color="coral", edgecolor="black")
    ax.set_title("Distribution of first digit in drawn 4D numbers")
    ax.set_xlabel("First digit")
    ax.set_ylabel("Count")
    plt.xticks(rotation=0)
    plt.tight_layout()
    if save:
        fig.savefig(Path(save), dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


def plot_prize_type_breakdown(
    long_df: pl.DataFrame,
    save: str | Path | None = None,
    figsize: tuple[float, float] = (6, 4),
) -> None:
    """Count of numbers by prize type (1st, 2nd, 3rd, special, consolation)."""
    pdf = long_df.to_pandas()
    counts = pdf["prize_type"].value_counts()

    fig, ax = plt.subplots(figsize=figsize)
    counts.plot(kind="bar", ax=ax, color=sns.color_palette("Set2"))
    ax.set_title("Count by prize type")
    ax.set_ylabel("Count")
    plt.xticks(rotation=20)
    plt.tight_layout()
    if save:
        fig.savefig(Path(save), dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()
