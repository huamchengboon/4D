#!/usr/bin/env python3
"""
Backtest every 4D number 0000–9999: bet RM1 on that exact number every draw.
Single pass over data with Polars; reports which numbers would have made the most profit.
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import polars as pl

from analysis.load import (
    DATE_COL,
    DEFAULT_CSV,
    load_history,
    PRIZE_1ST,
    PRIZE_2ND,
    PRIZE_3RD,
    SPECIAL_COL,
    CONSOLATION_COL,
)
from analysis.prizes import (
    MAGNUM_PRIZE_1ST,
    MAGNUM_PRIZE_2ND,
    MAGNUM_PRIZE_3RD,
    MAGNUM_PRIZE_SPECIAL,
    MAGNUM_PRIZE_CONSOLATION,
    MAGNUM_SMALL_PRIZE_1ST,
    MAGNUM_SMALL_PRIZE_2ND,
    MAGNUM_SMALL_PRIZE_3RD,
    MAGNUM_SMALL_PRIZE_SPECIAL,
    MAGNUM_SMALL_PRIZE_CONSOLATION,
)


def _prizes(small: bool) -> tuple[int, int, int, int, int]:
    """Return (1st, 2nd, 3rd, special, consolation) per RM1 for Big or Small."""
    if small:
        return (
            MAGNUM_SMALL_PRIZE_1ST,
            MAGNUM_SMALL_PRIZE_2ND,
            MAGNUM_SMALL_PRIZE_3RD,
            MAGNUM_SMALL_PRIZE_SPECIAL,
            MAGNUM_SMALL_PRIZE_CONSOLATION,
        )
    return (
        MAGNUM_PRIZE_1ST,
        MAGNUM_PRIZE_2ND,
        MAGNUM_PRIZE_3RD,
        MAGNUM_PRIZE_SPECIAL,
        MAGNUM_PRIZE_CONSOLATION,
    )


def run_backtest_all_numbers(
    csv_path: Path | None = None,
    operator: str | None = None,
    top_n: int = 30,
    bottom_n: int = 10,
    small: bool = False,
) -> pl.DataFrame:
    """
    One Polars pipeline: load draws, flatten all (number, prize) pairs, aggregate by number.
    small=True uses Magnum Small prizes (1st 3500, 2nd 2000, 3rd 1000; Special/Consolation 0).
    Returns full 10000-row DataFrame with columns: number, total_winnings_rm, n_draws, cost_rm, profit_rm,
    sorted by profit_rm descending. Also computes rank.
    """
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    p1, p2, p3, p_spec, p_cons = _prizes(small)

    df = load_history(str(path))
    if operator is not None:
        df = df.filter(pl.col("operator") == operator)
    if df.height == 0:
        raise ValueError("No draws after filter")

    n_draws = df.height
    cost_per_draw = 1.0

    # Ensure string columns
    df = df.with_columns(
        pl.col(PRIZE_1ST).cast(pl.Utf8),
        pl.col(PRIZE_2ND).cast(pl.Utf8),
        pl.col(PRIZE_3RD).cast(pl.Utf8),
        pl.col(SPECIAL_COL).cast(pl.Utf8),
        pl.col(CONSOLATION_COL).cast(pl.Utf8),
    )

    # Normalize to 4-digit
    def norm_expr(c: str) -> pl.Expr:
        return pl.col(c).str.strip_chars().str.zfill(4)

    # 1st prize rows
    first = (
        df.select(norm_expr(PRIZE_1ST).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p1).alias("prize"))
    )
    second = (
        df.select(norm_expr(PRIZE_2ND).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p2).alias("prize"))
    )
    third = (
        df.select(norm_expr(PRIZE_3RD).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p3).alias("prize"))
    )

    # Special: split and explode (column becomes list elements, then we get one row per element)
    special = (
        df.select(pl.col(SPECIAL_COL).str.split(",").alias("_list"))
        .explode("_list")
        .with_columns(pl.col("_list").str.strip_chars().str.zfill(4).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p_spec).alias("prize"))
        .select("number", "prize")
    )
    consolation = (
        df.select(pl.col(CONSOLATION_COL).str.split(",").alias("_list"))
        .explode("_list")
        .with_columns(pl.col("_list").str.strip_chars().str.zfill(4).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p_cons).alias("prize"))
        .select("number", "prize")
    )

    # Stack all
    long = pl.concat(
        [
            first.select("number", "prize"),
            second.select("number", "prize"),
            third.select("number", "prize"),
            special,
            consolation,
        ],
        how="vertical_relaxed",
    )

    # Aggregate winnings per number
    winnings = long.group_by("number").agg(pl.col("prize").sum().alias("total_winnings_rm"))

    # Full grid 0000-9999
    all_numbers = pl.DataFrame({"number": [f"{i:04d}" for i in range(10_000)]})
    result = (
        all_numbers
        .join(winnings, on="number", how="left")
        .with_columns(pl.col("total_winnings_rm").fill_null(0))
        .with_columns(
            pl.lit(n_draws).alias("n_draws"),
            pl.lit(n_draws * cost_per_draw).alias("cost_rm"),
        )
        .with_columns((pl.col("total_winnings_rm") - pl.col("cost_rm")).alias("profit_rm"))
        .sort("profit_rm", descending=True)
        .with_columns((pl.int_range(1, pl.len() + 1)).alias("rank"))
    )
    return result


def run_backtest_all_numbers_by_year(
    csv_path: Path | None = None,
    operator: str | None = None,
    top_per_year: int = 5,
    small: bool = False,
) -> pl.DataFrame:
    """
    Same backtest (RM1 straight per number per draw) but grouped by year.
    small=True uses Magnum Small prizes (1st/2nd/3rd only; Special/Consolation 0).
    Returns a DataFrame with one row per year: year, n_draws, and top_per_year columns
    (top1_number, top1_profit_rm, top2_number, top2_profit_rm, ...).
    """
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    p1, p2, p3, p_spec, p_cons = _prizes(small)

    df = load_history(str(path))
    if operator is not None:
        df = df.filter(pl.col("operator") == operator)
    if df.height == 0:
        raise ValueError("No draws after filter")

    df = df.with_columns(pl.col(DATE_COL).dt.year().alias("year"))
    cost_per_draw = 1.0

    df = df.with_columns(
        pl.col(PRIZE_1ST).cast(pl.Utf8),
        pl.col(PRIZE_2ND).cast(pl.Utf8),
        pl.col(PRIZE_3RD).cast(pl.Utf8),
        pl.col(SPECIAL_COL).cast(pl.Utf8),
        pl.col(CONSOLATION_COL).cast(pl.Utf8),
    )

    def norm_expr(c: str) -> pl.Expr:
        return pl.col(c).str.strip_chars().str.zfill(4)

    # Build long with year
    first = (
        df.select(pl.col("year"), norm_expr(PRIZE_1ST).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p1).alias("prize"))
    )
    second = (
        df.select(pl.col("year"), norm_expr(PRIZE_2ND).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p2).alias("prize"))
    )
    third = (
        df.select(pl.col("year"), norm_expr(PRIZE_3RD).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p3).alias("prize"))
    )
    special = (
        df.select(pl.col("year"), pl.col(SPECIAL_COL).str.split(",").alias("_list"))
        .explode("_list")
        .with_columns(pl.col("_list").str.strip_chars().str.zfill(4).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p_spec).alias("prize"))
        .select("year", "number", "prize")
    )
    consolation = (
        df.select(pl.col("year"), pl.col(CONSOLATION_COL).str.split(",").alias("_list"))
        .explode("_list")
        .with_columns(pl.col("_list").str.strip_chars().str.zfill(4).alias("number"))
        .filter(pl.col("number").str.len_chars() == 4)
        .with_columns(pl.lit(p_cons).alias("prize"))
        .select("year", "number", "prize")
    )

    long = pl.concat(
        [
            first.select("year", "number", "prize"),
            second.select("year", "number", "prize"),
            third.select("year", "number", "prize"),
            special,
            consolation,
        ],
        how="vertical_relaxed",
    )

    winnings = long.group_by(["year", "number"]).agg(pl.col("prize").sum().alias("total_winnings_rm"))
    draws_per_year = df.group_by("year").agg(pl.len().alias("n_draws"))
    all_years = draws_per_year.select("year")
    all_numbers = pl.DataFrame({"number": [f"{i:04d}" for i in range(10_000)]})
    # Cartesian: every (year, number)
    year_numbers = all_years.join(all_numbers, how="cross")
    with_cost = year_numbers.join(draws_per_year, on="year", how="left").join(
        winnings, on=["year", "number"], how="left"
    )
    with_cost = with_cost.with_columns(
        pl.col("total_winnings_rm").fill_null(0),
        (pl.col("total_winnings_rm") - pl.col("n_draws") * cost_per_draw).alias("profit_rm"),
    )

    # For each year, rank by profit and take top_per_year
    with_rank = with_cost.with_columns(
        pl.col("profit_rm").rank("ordinal", descending=True).over("year").alias("rank")
    )
    top_per_year_df = with_rank.filter(pl.col("rank") <= top_per_year).sort(["year", "rank"])

    # Pivot to one row per year: year, n_draws, top1_number, top1_profit, ...
    rows = []
    for year in top_per_year_df["year"].unique().sort():
        sub = top_per_year_df.filter(pl.col("year") == year)
        n_draws = sub["n_draws"][0]
        row = {"year": year, "n_draws": n_draws}
        for r in range(1, top_per_year + 1):
            rrow = sub.filter(pl.col("rank") == r)
            if rrow.height > 0:
                row[f"top{r}_number"] = rrow["number"][0]
                row[f"top{r}_profit_rm"] = rrow["profit_rm"][0]
            else:
                row[f"top{r}_number"] = None
                row[f"top{r}_profit_rm"] = None
        rows.append(row)
    return pl.DataFrame(rows)


def _main_by_year(console: "Console", args: "argparse.Namespace") -> None:
    from rich.panel import Panel
    from rich.table import Table

    operators = [None] + load_history(str(args.csv or DEFAULT_CSV))["operator"].unique().sort().to_list()
    op_labels = ["All operators"] + [str(o) for o in load_history(str(args.csv or DEFAULT_CSV))["operator"].unique().sort().to_list()]
    top_per_year = 3

    for op, label in zip(operators, op_labels):
        try:
            by_year = run_backtest_all_numbers_by_year(csv_path=args.csv, operator=op, top_per_year=top_per_year, small=getattr(args, "small", False))
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]{e}[/]")
            continue
        bet_type = "Small (1st/2nd/3rd only)" if getattr(args, "small", False) else "Big (1st, 2nd, 3rd, Special, Consolation)"
        console.print(Panel(
            f"[bold]{label}[/] — Top {top_per_year} numbers by profit each year (RM1 straight/draw, [dim]{bet_type}[/]).",
            border_style="cyan",
        ))
        t = Table(show_header=True)
        t.add_column("Year", justify="right")
        t.add_column("Draws", justify="right")
        for r in range(1, top_per_year + 1):
            t.add_column(f"#{r} Number", justify="center")
            t.add_column(f"#{r} Profit (RM)", justify="right")
        for row in by_year.iter_rows(named=True):
            rlist = [str(row["year"]), str(row["n_draws"])]
            for r in range(1, top_per_year + 1):
                num = row.get(f"top{r}_number") or "—"
                profit = row.get(f"top{r}_profit_rm")
                if profit is not None:
                    style = "green" if profit >= 0 else "red"
                    rlist.append(str(num))
                    rlist.append(f"[{style}]{profit:+,.0f}[/]")
                else:
                    rlist.append("—")
                    rlist.append("—")
            t.add_row(*rlist)
        console.print(t)
        console.print()


def main() -> None:
    import argparse
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    parser = argparse.ArgumentParser(description="Backtest 0000-9999 straight (RM1/draw), report best/worst")
    parser.add_argument("--csv", type=Path, default=None, help="Path to 4d_history.csv")
    parser.add_argument("--operator", type=str, default=None, help="Filter by operator (default: all)")
    parser.add_argument("--top", type=int, default=30, help="Show top N by profit")
    parser.add_argument("--bottom", type=int, default=10, help="Show bottom N (most loss)")
    parser.add_argument("--all", action="store_true", help="Print all 10000 (to stdout, no Rich)")
    parser.add_argument("--by-year", action="store_true", help="Profit grouped by year; show top numbers per year for all operators and each operator")
    parser.add_argument("--small", action="store_true", help="Use Magnum Small prizes (1st 3500, 2nd 2000, 3rd 1000; Special/Consolation 0)")
    args = parser.parse_args()

    console = Console()

    if args.by_year:
        _main_by_year(console, args)
        return

    op_label = args.operator or "All operators"
    bet_label = "Small (1st/2nd/3rd only)" if args.small else "Big (1st, 2nd, 3rd, Special, Consolation)"
    console.print(Panel(f"[bold]Backtest each number 0000–9999 (RM1 straight per draw, [dim]{bet_label}[/]) — {op_label}[/]", border_style="cyan"))

    try:
        result = run_backtest_all_numbers(
            csv_path=args.csv,
            operator=args.operator,
            top_n=args.top,
            bottom_n=args.bottom,
            small=args.small,
        )
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)

    n_draws = result["n_draws"][0]
    cost_rm = result["cost_rm"][0]

    if args.all:
        result.write_csv(sys.stdout)
        return

    # Top by profit
    top = result.head(args.top)
    t = Table(title=f"Top {args.top} by profit (RM1/draw, {n_draws} draws, cost RM {cost_rm:,.0f} per number)")
    t.add_column("Rank", justify="right", style="dim")
    t.add_column("Number", justify="center")
    t.add_column("Winnings (RM)", justify="right")
    t.add_column("Profit (RM)", justify="right")
    for row in top.iter_rows(named=True):
        style = "green" if row["profit_rm"] >= 0 else ""
        t.add_row(
            str(row["rank"]),
            row["number"],
            f"{row['total_winnings_rm']:,.0f}",
            f"[{style}]{row['profit_rm']:+,.0f}[/]",
        )
    console.print(t)

    # Bottom (worst)
    worst = result.tail(args.bottom).reverse()
    t2 = Table(title=f"Bottom {args.bottom} (largest loss)")
    t2.add_column("Rank", justify="right", style="dim")
    t2.add_column("Number", justify="center")
    t2.add_column("Winnings (RM)", justify="right")
    t2.add_column("Profit (RM)", justify="right")
    for row in worst.iter_rows(named=True):
        t2.add_row(
            str(row["rank"]),
            row["number"],
            f"{row['total_winnings_rm']:,.0f}",
            f"[red]{row['profit_rm']:+,.0f}[/]",
        )
    console.print(t2)

    best = result.row(0, named=True)
    console.print()
    console.print(f"  [bold]Best number:[/] [green]{best['number']}[/] — profit RM {best['profit_rm']:+,.0f} (winnings {best['total_winnings_rm']:,.0f} − cost {cost_rm:,.0f})")
    n_profit = result.filter(pl.col("profit_rm") > 0).height
    console.print(f"  [dim]Numbers with positive profit: {n_profit} / 10000[/]")


if __name__ == "__main__":
    main()
