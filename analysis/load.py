"""
Load and transform 4D history CSV.
Polars for fast I/O and transformations.
"""

from pathlib import Path

import polars as pl

# Default path relative to project root
DEFAULT_CSV = Path(__file__).resolve().parent.parent / "4d_history.csv"

DATE_COL = "date"
OPERATOR_COL = "operator"
DRAW_NO_COL = "draw_no"
PRIZE_1ST = "1st"
PRIZE_2ND = "2nd"
PRIZE_3RD = "3rd"
SPECIAL_COL = "special"
CONSOLATION_COL = "consolation"

PRIZE_TYPES = ("1st", "2nd", "3rd", "special", "consolation")


def load_history(csv_path: str | Path | None = None) -> pl.DataFrame:
    """
    Load 4d_history.csv into a Polars DataFrame.
    date parsed as Date; other columns as UTF-8 strings.
    """
    path = Path(csv_path) if csv_path else DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = pl.read_csv(
        path,
        try_parse_dates=True,
        infer_schema_length=10_000,
    )
    if df.schema.get(DATE_COL) != pl.Date:
        df = df.with_columns(pl.col(DATE_COL).str.to_date())
    return df


def get_draws_long(df: pl.DataFrame) -> pl.DataFrame:
    """
    Long format: one row per (date, operator, draw_no, prize_type, number).
    Uses Polars only (no row iteration).
    """
    # Ensure prize columns are string (preserve leading zeros e.g. 0123)
    df = df.with_columns(
        pl.col(PRIZE_1ST).cast(pl.Utf8),
        pl.col(PRIZE_2ND).cast(pl.Utf8),
        pl.col(PRIZE_3RD).cast(pl.Utf8),
        pl.col(SPECIAL_COL).cast(pl.Utf8),
        pl.col(CONSOLATION_COL).cast(pl.Utf8),
    )

    # Top 3 prizes: one number per row
    top = df.select(
        pl.col(DATE_COL),
        pl.col(OPERATOR_COL),
        pl.col(DRAW_NO_COL),
        pl.col(PRIZE_1ST).alias("number"),
        pl.lit(PRIZE_1ST).alias("prize_type"),
    ).filter(pl.col("number").str.len_chars() > 0)
    top2 = df.select(
        pl.col(DATE_COL), pl.col(OPERATOR_COL), pl.col(DRAW_NO_COL),
        pl.col(PRIZE_2ND).alias("number"), pl.lit(PRIZE_2ND).alias("prize_type"),
    ).filter(pl.col("number").str.len_chars() > 0)
    top3 = df.select(
        pl.col(DATE_COL), pl.col(OPERATOR_COL), pl.col(DRAW_NO_COL),
        pl.col(PRIZE_3RD).alias("number"), pl.lit(PRIZE_3RD).alias("prize_type"),
    ).filter(pl.col("number").str.len_chars() > 0)

    # Special: split comma-separated then explode, strip whitespace
    special = (
        df.select(pl.col(DATE_COL), pl.col(OPERATOR_COL), pl.col(DRAW_NO_COL), pl.col(SPECIAL_COL).str.split(",").alias("_nums"))
        .explode("_nums")
        .with_columns(pl.col("_nums").str.strip_chars().cast(pl.Utf8).alias("number"), pl.lit("special").alias("prize_type"))
        .select(pl.col(DATE_COL), pl.col(OPERATOR_COL), pl.col(DRAW_NO_COL), pl.col("number"), pl.col("prize_type"))
        .filter(pl.col("number").str.len_chars() > 0)
    )
    consolation = (
        df.select(pl.col(DATE_COL), pl.col(OPERATOR_COL), pl.col(DRAW_NO_COL), pl.col(CONSOLATION_COL).str.split(",").alias("_nums"))
        .explode("_nums")
        .with_columns(pl.col("_nums").str.strip_chars().cast(pl.Utf8).alias("number"), pl.lit("consolation").alias("prize_type"))
        .select(pl.col(DATE_COL), pl.col(OPERATOR_COL), pl.col(DRAW_NO_COL), pl.col("number"), pl.col("prize_type"))
        .filter(pl.col("number").str.len_chars() > 0)
    )

    return pl.concat([top, top2, top3, special, consolation], how="vertical_relaxed")


def get_number_frequencies(
    df: pl.DataFrame,
    by_operator: bool = False,
    prize_types: tuple[str, ...] | None = None,
) -> pl.DataFrame:
    """
    Count how often each 4D number appears.
    Returns: number, count [, operator].
    """
    long = get_draws_long(df)
    if prize_types:
        long = long.filter(pl.col("prize_type").is_in(list(prize_types)))
    if by_operator:
        return long.group_by([OPERATOR_COL, "number"]).agg(pl.len().alias("count")).sort("count", descending=True)
    return long.group_by("number").agg(pl.len().alias("count")).sort("count", descending=True)


def get_draws_as_sets(df: pl.DataFrame) -> list[tuple[str, str, set[str]]]:
    """
    One entry per draw (row): (date_str, operator, set of all winning numbers).
    For RL backtest: at step t we predict, then compare with draw[t].
    """
    df = df.with_columns(
        pl.col(PRIZE_1ST).cast(pl.Utf8),
        pl.col(PRIZE_2ND).cast(pl.Utf8),
        pl.col(PRIZE_3RD).cast(pl.Utf8),
        pl.col(SPECIAL_COL).cast(pl.Utf8),
        pl.col(CONSOLATION_COL).cast(pl.Utf8),
    )
    out = []
    for row in df.iter_rows(named=True):
        nums = set()
        for key in (PRIZE_1ST, PRIZE_2ND, PRIZE_3RD):
            v = row.get(key)
            if v is not None and str(v).strip():
                nums.add(str(v).strip())
        for key in (SPECIAL_COL, CONSOLATION_COL):
            v = row.get(key)
            if v is not None:
                for n in str(v).split(","):
                    n = n.strip()
                    if n:
                        nums.add(n)
        date_str = str(row[DATE_COL])
        op = str(row[OPERATOR_COL])
        out.append((date_str, op, nums))
    return out


def _norm(s: str) -> str:
    return str(s).strip().zfill(4)


def get_draws_with_prizes(df: pl.DataFrame) -> list[dict]:
    """
    One entry per draw (row): dict with 1st, 2nd, 3rd (str), special, consolation (list of str).
    Numbers are normalized to 4-digit. Same order as get_draws_as_sets(df).
    """
    df = df.with_columns(
        pl.col(PRIZE_1ST).cast(pl.Utf8),
        pl.col(PRIZE_2ND).cast(pl.Utf8),
        pl.col(PRIZE_3RD).cast(pl.Utf8),
        pl.col(SPECIAL_COL).cast(pl.Utf8),
        pl.col(CONSOLATION_COL).cast(pl.Utf8),
    )
    out = []
    for row in df.iter_rows(named=True):
        first = row.get(PRIZE_1ST)
        second = row.get(PRIZE_2ND)
        third = row.get(PRIZE_3RD)
        special_str = row.get(SPECIAL_COL) or ""
        consolation_str = row.get(CONSOLATION_COL) or ""
        special = [_norm(n) for n in special_str.split(",") if n and n.strip()]
        consolation = [_norm(n) for n in consolation_str.split(",") if n and n.strip()]
        out.append({
            "1st": _norm(first) if first and str(first).strip() else None,
            "2nd": _norm(second) if second and str(second).strip() else None,
            "3rd": _norm(third) if third and str(third).strip() else None,
            "special": special,
            "consolation": consolation,
        })
    return out
