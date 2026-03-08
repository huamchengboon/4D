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


def _precompute_winnings_4d_3d(draws: list[dict], progress: bool = False) -> list[float]:
    """
    One pass over all draws: for each number 0-9999, sum 4D+3D prizes (best per draw).
    Returns list of length 10000: total winnings for number i (as index).
    """
    # winnings[i] = total RM won by number i (index 0-9999) across all draws
    winnings = [0.0] * 10_000
    it = tqdm(draws, desc="Precompute winnings", unit="draw", disable=not progress)
    for d in it:
        # Build prize for this draw: at most 23 4D + up to 30 3D (10 numbers × 3 tiers)
        # 4D takes precedence over 3D. Only accumulate non-zero entries.
        draw_prize: dict[int, float] = {}
        first = d.get("1st")
        second = d.get("2nd")
        third = d.get("3rd")
        special = set(d.get("special") or [])
        consolation = set(d.get("consolation") or [])

        def set4d(num_str: str, prize: float) -> None:
            if num_str and len(num_str) >= 4:
                idx = int(_norm(num_str))
                if 0 <= idx < 10_000:
                    draw_prize[idx] = prize

        if first:
            set4d(first, float(MAGNUM_PRIZE_1ST))
        if second:
            set4d(second, float(MAGNUM_PRIZE_2ND))
        if third:
            set4d(third, float(MAGNUM_PRIZE_3RD))
        for n in special:
            set4d(n, float(MAGNUM_PRIZE_SPECIAL))
        for n in consolation:
            set4d(n, float(MAGNUM_PRIZE_CONSOLATION))

        # 3D: last 3 digits match 1st/2nd/3rd (only if 4D not won)
        def set3d(last3_str: str, prize: float) -> None:
            if not last3_str or len(last3_str) < 3:
                return
            last3 = int(last3_str.strip().zfill(4)[-3:])
            for first_d in range(10):
                idx = first_d * 1000 + last3
                if idx not in draw_prize:
                    draw_prize[idx] = prize

        if first:
            set3d(_last3(first), float(MAGNUM_3D_BIG_1ST))
        if second:
            set3d(_last3(second), float(MAGNUM_3D_BIG_2ND))
        if third:
            set3d(_last3(third), float(MAGNUM_3D_BIG_3RD))

        for idx, p in draw_prize.items():
            winnings[idx] += p
    return winnings


def multiset_to_24(multiset: str) -> list[str]:
    """Four distinct digits -> 24 permutations as 4-digit strings."""
    s = multiset.strip().zfill(4)
    if len(s) != 4 or len(set(s)) != 4:
        raise ValueError("Multiset must be 4 distinct digits")
    return ["".join(p) for p in permutations(s, 4)]


def all_multisets() -> list[str]:
    """All 210 multisets (4 distinct digits)."""
    return ["".join(str(d) for d in c) for c in combinations(range(10), 4)]


def get_precomputed_winnings(
    operator: str | None = None,
    csv_path: Path | None = None,
    *,
    progress: bool = True,
) -> tuple[list[float], int]:
    """
    Load draws, precompute 4D+3D winnings for each number 0-9999. Return (winnings list, n_draws).
    Reuse this for both best-multiset and top-24-individual strategies.
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
    n_draws = len(draws)
    winnings = _precompute_winnings_4d_3d(draws, progress=progress)
    return winnings, n_draws


def run_best_multiset_backtest(
    operator: str | None = None,
    csv_path: Path | None = None,
    *,
    progress: bool = True,
    _winnings: list[float] | None = None,
    _n_draws: int | None = None,
) -> tuple[str, list[str], dict]:
    """
    For each of 210 multisets, run 24-number 4D+3D backtest. Return (best_multiset, best_24_numbers, result_dict).
    Uses one-pass precomputation of per-number winnings (CPU only, no GPU), then O(210×24) lookups.
    """
    if _winnings is not None and _n_draws is not None:
        winnings = _winnings
        n_draws = _n_draws
    else:
        winnings, n_draws = get_precomputed_winnings(operator=operator, csv_path=csv_path, progress=progress)
    cost_per_draw = COST_PER_DRAW

    best_multiset = None
    best_numbers = None
    best_profit = -float("inf")
    best_result = None

    multisets = all_multisets()
    bar = tqdm(multisets, desc="Scanning 210 multisets", unit="ms", disable=not progress)
    for ms in bar:
        numbers = multiset_to_24(ms)
        total_win = sum(winnings[int(n)] for n in numbers)
        profit = total_win - n_draws * cost_per_draw
        if profit > best_profit:
            best_profit = profit
            best_multiset = ms
            best_numbers = numbers
            best_result = {
                "cost_rm": n_draws * cost_per_draw,
                "total_winnings_rm": total_win,
                "profit_rm": profit,
                "n_draws": n_draws,
            }
        bar.set_postfix(
            best=best_multiset or "-",
            best_profit=f"{best_profit:+,.0f}" if best_profit > -float("inf") else "-",
            current=f"{profit:+,.0f}",
        )

    return best_multiset, best_numbers or [], best_result or {}


def run_top24_individual_backtest(
    operator: str | None = None,
    csv_path: Path | None = None,
    *,
    progress: bool = True,
    _winnings: list[float] | None = None,
    _n_draws: int | None = None,
) -> tuple[list[str], dict]:
    """
    Pick the 24 individual numbers (from 0000-9999) with highest 4D+3D profit when bet RM1 each.
    They need not be from one multiset. Return (list of 24 numbers, result_dict).
    Uses precomputed winnings so it's fast.
    """
    if _winnings is not None and _n_draws is not None:
        winnings = _winnings
        n_draws = _n_draws
    else:
        winnings, n_draws = get_precomputed_winnings(operator=operator, csv_path=csv_path, progress=progress)

    cost_per_draw = COST_PER_DRAW
    # profit[i] = winnings[i] - n_draws (one number costs n_draws over history)
    profits = [(f"{i:04d}", winnings[i] - n_draws) for i in range(10_000)]
    profits.sort(key=lambda x: -x[1])
    top24 = [p[0] for p in profits[:24]]
    total_win = sum(winnings[int(n)] for n in top24)
    res = {
        "cost_rm": n_draws * cost_per_draw,
        "total_winnings_rm": total_win,
        "profit_rm": total_win - n_draws * cost_per_draw,
        "n_draws": n_draws,
    }
    return top24, res


def _main_by_operator(console: "Console", args: "argparse.Namespace") -> None:
    from rich.panel import Panel
    from rich.table import Table

    path = args.csv or DEFAULT_CSV
    if not path.is_file():
        console.print(f"[red]CSV not found: {path}[/]")
        return
    df = load_history(str(path))
    operators = df["operator"].unique().sort().to_list()
    progress = not getattr(args, "quiet", False)

    console.print(Panel("[bold]Best 24 numbers per operator (4D+3D Big, RM1×24 per draw)[/]", border_style="cyan"))
    console.print("Each operator uses only its own draws; the 24 numbers are the top 24 by profit for that operator.\n")

    results = []
    for op in tqdm(operators, desc="By operator", unit="op", disable=not progress):
        op_str = str(op)
        try:
            winnings, n_draws = get_precomputed_winnings(
                operator=op_str, csv_path=path, progress=False
            )
            top24, res = run_top24_individual_backtest(_winnings=winnings, _n_draws=n_draws)
            results.append((op_str, n_draws, top24, res))
        except Exception as e:
            console.print(f"[red]{op_str}: {e}[/]")

    for op_str, n_draws, top24, res in results:
        profit = res["profit_rm"]
        style = "green" if profit >= 0 else "red"
        console.print(Panel(
            f"[bold]{op_str}[/] — {n_draws} draws | Cost RM {res['cost_rm']:,.0f} | Winnings RM {res['total_winnings_rm']:,.0f} | Profit [{style}]{profit:+,.0f}[/] RM",
            border_style="blue",
        ))
        console.print(f"  24 numbers: {', '.join(sorted(top24))}")
        console.print()

    console.print("[bold]Summary[/]")
    t = Table(show_header=True, header_style="bold")
    t.add_column("Operator", style="dim")
    t.add_column("Draws", justify="right")
    t.add_column("Profit (RM)", justify="right")
    for op_str, n_draws, _top24, res in results:
        p = res["profit_rm"]
        t.add_row(op_str, str(n_draws), f"[{'green' if p >= 0 else 'red'}]{p:+,.0f}[/]")
    console.print(t)


def main() -> None:
    import argparse
    from rich.console import Console
    from rich.panel import Panel

    parser = argparse.ArgumentParser(description="Find best 24-number strategy (4D+3D Big), same 24 for all draws")
    parser.add_argument("--operator", type=str, default=None, help="Filter operator (default: all)")
    parser.add_argument("--by-operator", action="store_true", help="Show best 24 numbers per operator (Magnum, Sports Toto, Da Ma Cai)")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true", help="Disable tqdm progress bars")
    args = parser.parse_args()
    progress = not args.quiet

    console = Console()

    if args.by_operator:
        _main_by_operator(console, args)
        return

    op_label = args.operator or "All operators"
    console.print(Panel(f"[bold]24-number strategy backtest (4D + 3D Big, RM1×24 per draw) — {op_label}[/]", border_style="cyan"))

    # Precompute once; use for both strategies
    try:
        winnings, n_draws = get_precomputed_winnings(
            operator=args.operator, csv_path=args.csv, progress=progress
        )
    except Exception as e:
        console.print(f"[red]{e}[/]")
        return

    # Hypothesis 1: Best multiset (24 = permutations of one multiset)
    console.print("\n[bold]Hypothesis 1:[/] Best multiset — 24 numbers = all permutations of one multiset.")
    try:
        best_ms, best_nums, res = run_best_multiset_backtest(
            _winnings=winnings, _n_draws=n_draws, progress=progress
        )
        console.print(f"  Best multiset: [green]{best_ms}[/]")
        console.print(f"  Cost: RM {res['cost_rm']:,.0f}  |  Winnings: RM {res['total_winnings_rm']:,.0f}  |  Profit: [{'green' if res['profit_rm'] >= 0 else 'red'}]{res['profit_rm']:+,.0f}[/]")
        console.print(f"  24 numbers: {', '.join(sorted(best_nums))}")
    except Exception as e:
        console.print(f"  [red]{e}[/]")
        res = None
        best_ms = None
        best_nums = None

    # Hypothesis 2: Top 24 individual numbers (any 0000-9999, need not be one multiset)
    console.print("\n[bold]Hypothesis 2:[/] Top 24 individual numbers — the 24 most profitable numbers (any, not necessarily from one multiset).")
    try:
        top24, res2 = run_top24_individual_backtest(_winnings=winnings, _n_draws=n_draws)
        console.print(f"  Cost: RM {res2['cost_rm']:,.0f}  |  Winnings: RM {res2['total_winnings_rm']:,.0f}  |  Profit: [{'green' if res2['profit_rm'] >= 0 else 'red'}]{res2['profit_rm']:+,.0f}[/]")
        console.print(f"  24 numbers: {', '.join(sorted(top24))}")
    except Exception as e:
        console.print(f"  [red]{e}[/]")
        res2 = None
        top24 = None

    # Compare and report best
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
    console.print(f"  24 numbers: {', '.join(sorted(best_nums_final))}")
    if best_profit >= 0:
        console.print("  [green]Use the 24 numbers above; same set for all draws and operators.[/]")
    else:
        console.print("  [dim]No strategy achieved profit.[/]")


if __name__ == "__main__":
    main()
