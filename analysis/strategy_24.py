"""
Strategy backtest: pick 24 numbers (fixed for all draws, all operators).
Uses 4D Big prizes + 3D (last 3 digits) Big prizes. One prize per number per draw (best match).
"""

from __future__ import annotations

import sys
from itertools import combinations, permutations
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import polars as pl
from tqdm import tqdm

from analysis.load import DEFAULT_CSV, load_history, get_draws_with_prizes
from analysis.prizes import (
    MAGNUM_PRIZE_1ST,
    MAGNUM_PRIZE_2ND,
    MAGNUM_PRIZE_3RD,
    MAGNUM_PRIZE_SPECIAL,
    MAGNUM_PRIZE_CONSOLATION,
    MAGNUM_3D_BIG_1ST,
    MAGNUM_3D_BIG_2ND,
    MAGNUM_3D_BIG_3RD,
)

COST_PER_DRAW = 24.0  # RM1 × 24 numbers


def _norm(s: str) -> str:
    return str(s).strip().zfill(4)


def _last3(num: str) -> str:
    return _norm(num)[-3:]


def prize_one_number(num: str, draw: dict) -> float:
    """
    One number, one draw, RM1 bet (Big). Returns 4D prize if full match, else 3D prize if last 3 match.
    One prize per number (best only).
    """
    n = _norm(num)
    first = draw.get("1st")
    second = draw.get("2nd")
    third = draw.get("3rd")
    special = set(draw.get("special") or [])
    consolation = set(draw.get("consolation") or [])

    if first and n == first:
        return float(MAGNUM_PRIZE_1ST)
    if second and n == second:
        return float(MAGNUM_PRIZE_2ND)
    if third and n == third:
        return float(MAGNUM_PRIZE_3RD)
    if n in special:
        return float(MAGNUM_PRIZE_SPECIAL)
    if n in consolation:
        return float(MAGNUM_PRIZE_CONSOLATION)

    # No 4D match — check 3D (last 3 digits)
    l3 = _last3(n)
    if first and _last3(first) == l3:
        return float(MAGNUM_3D_BIG_1ST)
    if second and _last3(second) == l3:
        return float(MAGNUM_3D_BIG_2ND)
    if third and _last3(third) == l3:
        return float(MAGNUM_3D_BIG_3RD)
    return 0.0


def backtest_24_numbers(
    numbers: list[str],
    draws: list[dict],
) -> dict:
    """
    numbers: list of 24 four-digit strings.
    draws: list of draw dicts (1st, 2nd, 3rd, special, consolation).
    Returns cost_rm, total_winnings_rm, profit_rm, n_draws.
    """
    if len(numbers) != 24:
        raise ValueError("Must provide exactly 24 numbers")
    n_draws = len(draws)
    cost_rm = n_draws * COST_PER_DRAW
    total = 0.0
    for d in draws:
        for num in numbers:
            total += prize_one_number(num, d)
    return {
        "cost_rm": cost_rm,
        "total_winnings_rm": total,
        "profit_rm": total - cost_rm,
        "n_draws": n_draws,
    }


def multiset_to_24(multiset: str) -> list[str]:
    """Four distinct digits -> 24 permutations as 4-digit strings."""
    s = multiset.strip().zfill(4)
    if len(s) != 4 or len(set(s)) != 4:
        raise ValueError("Multiset must be 4 distinct digits")
    return ["".join(p) for p in permutations(s, 4)]


def all_multisets() -> list[str]:
    """All 210 multisets (4 distinct digits)."""
    return ["".join(str(d) for d in c) for c in combinations(range(10), 4)]


def run_best_multiset_backtest(
    operator: str | None = None,
    csv_path: Path | None = None,
    *,
    progress: bool = True,
) -> tuple[str, list[str], dict]:
    """
    For each of 210 multisets, run 24-number 4D+3D backtest. Return (best_multiset, best_24_numbers, result_dict).
    """
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = load_history(str(path))
    if operator is not None:
        df = df.filter(pl.col("operator") == operator)
    if df.height == 0:
        raise ValueError("No draws")
    draws = get_draws_with_prizes(df)

    best_multiset = None
    best_numbers = None
    best_profit = -float("inf")
    best_result = None

    multisets = all_multisets()
    iterator = tqdm(multisets, desc="Scanning 210 multisets", unit="ms", disable=not progress)
    for ms in iterator:
        numbers = multiset_to_24(ms)
        res = backtest_24_numbers(numbers, draws)
        if res["profit_rm"] > best_profit:
            best_profit = res["profit_rm"]
            best_multiset = ms
            best_numbers = numbers
            best_result = res
        # Live update: current best and this multiset's profit
        iterator.set_postfix(
            best=best_multiset or "-",
            best_profit=f"{best_profit:+,.0f}" if best_profit > -float("inf") else "-",
            current=f"{res['profit_rm']:+,.0f}",
        )

    return best_multiset, best_numbers or [], best_result or {}


def run_top24_individual_backtest(
    operator: str | None = None,
    csv_path: Path | None = None,
    *,
    progress: bool = True,
) -> tuple[list[str], dict]:
    """
    Compute 4D+3D winnings for each number 0000-9999 when bet alone; take top 24 by profit.
    Backtest that set of 24. Return (list of 24 numbers, result_dict).
    """
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = load_history(str(path))
    if operator is not None:
        df = df.filter(pl.col("operator") == operator)
    draws = get_draws_with_prizes(df)
    n_draws = len(draws)
    cost_per_number = n_draws * 1.0

    # Per-number profit (4D+3D, RM1 per draw)
    profits = []
    for i in tqdm(range(10_000), desc="Scanning 10000 numbers", unit="num", disable=not progress):
        num = f"{i:04d}"
        winnings = sum(prize_one_number(num, d) for d in draws)
        profit = winnings - cost_per_number
        profits.append((num, profit))
    profits.sort(key=lambda x: -x[1])
    top24 = [p[0] for p in profits[:24]]

    res = backtest_24_numbers(top24, draws)
    return top24, res


def main() -> None:
    import argparse
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    parser = argparse.ArgumentParser(description="Find best 24-number strategy (4D+3D Big), same 24 for all draws")
    parser.add_argument("--operator", type=str, default=None, help="Filter operator (default: all)")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--top24", action="store_true", help="Also run Hypothesis 2 (top 24 individual; slow)")
    parser.add_argument("--quiet", action="store_true", help="Disable tqdm progress bars")
    args = parser.parse_args()
    progress = not args.quiet

    console = Console()
    op_label = args.operator or "All operators"
    console.print(Panel(f"[bold]24-number strategy backtest (4D + 3D Big, RM1×24 per draw) — {op_label}[/]", border_style="cyan"))

    # Strategy 1: Best multiset (24 permutations)
    console.print("\n[bold]Hypothesis 1:[/] Best multiset — 24 numbers = all permutations of the multiset with highest 4D+3D profit.")
    try:
        best_ms, best_nums, res = run_best_multiset_backtest(
            operator=args.operator, csv_path=args.csv, progress=progress
        )
        console.print(f"  Best multiset: [green]{best_ms}[/]")
        console.print(f"  Cost: RM {res['cost_rm']:,.0f}  |  Winnings: RM {res['total_winnings_rm']:,.0f}  |  Profit: [{'green' if res['profit_rm'] >= 0 else 'red'}]{res['profit_rm']:+,.0f}[/]")
        console.print(f"  24 numbers: {', '.join(sorted(best_nums))}")
        if res["profit_rm"] >= 0:
            console.print("  [green]Strategy 1 is profitable.[/]")
        else:
            console.print("  [yellow]Strategy 1 not profitable.[/]")
    except Exception as e:
        console.print(f"  [red]{e}[/]")
        res = None
        best_ms = None
        best_nums = None

    res2 = None
    top24 = None
    if args.top24:
        console.print("\n[bold]Hypothesis 2:[/] Top 24 numbers by individual 4D+3D profit (slow).")
        try:
            top24, res2 = run_top24_individual_backtest(
                operator=args.operator, csv_path=args.csv, progress=progress
            )
            console.print(f"  Cost: RM {res2['cost_rm']:,.0f}  |  Winnings: RM {res2['total_winnings_rm']:,.0f}  |  Profit: [{'green' if res2['profit_rm'] >= 0 else 'red'}]{res2['profit_rm']:+,.0f}[/]")
        except Exception as e:
            console.print(f"  [red]{e}[/]")

    # Report best
    console.print("\n" + "=" * 50)
    candidates = []
    if best_ms is not None and res:
        candidates.append(("Best multiset " + best_ms, res["profit_rm"], best_nums or [], res))
    if res2 and top24:
        candidates.append(("Top 24 individual", res2["profit_rm"], top24, res2))
    if not candidates:
        console.print("[red]No results.[/]")
        return
    best_label, best_profit, best_nums_final, best_res = max(candidates, key=lambda x: x[1])
    console.print(f"[bold]Best strategy:[/] {best_label} — Profit [{'green' if best_profit >= 0 else 'red'}]{best_profit:+,.0f}[/] RM")
    if best_profit >= 0:
        console.print("  [green]Use the 24 numbers above; same set for all draws and operators.[/]")
    else:
        console.print("  [dim]No strategy achieved profit.[/]")


if __name__ == "__main__":
    main()
