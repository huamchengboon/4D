#!/usr/bin/env python3
"""
Backtest i-box (position-ignored) strategy: bet RM1 on a fixed 4-digit number
as i-box on Magnum 4D. Payout depends on permutation count (24 for all-different).
"""

from __future__ import annotations

import sys
from collections import defaultdict
from itertools import combinations, permutations
from pathlib import Path

import polars as pl

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from analysis.load import (
    DEFAULT_CSV,
    DATE_COL,
    load_history,
    get_draws_with_prizes,
)
from analysis.prizes import (
    MAGNUM_PRIZE_1ST,
    MAGNUM_PRIZE_2ND,
    MAGNUM_PRIZE_3RD,
    MAGNUM_PRIZE_SPECIAL,
    MAGNUM_PRIZE_CONSOLATION,
)

# Magnum 4D i-box Big forecast, RM1 bet (24 permutations = all different digits)
IBOX_PRIZE_1ST = 105
IBOX_PRIZE_2ND = 42
IBOX_PRIZE_3RD = 21
IBOX_PRIZE_SPECIAL = 8
IBOX_PRIZE_CONSOLATION = 3

# Straight (combo) bet: RM1 per number, 24 numbers = RM24 per draw
STRAIGHT_COST_PER_DRAW = 24.0

# Top over multisets from pattern analysis (Magnum 4D only)
TOP_OVER_MULTISETS_MAGNUM = ["1347", "5789", "0178", "2358", "1248"]


def ibox_permutations(digits: str) -> set[str]:
    """Return set of 4-digit strings for all permutations (e.g. 1347 -> 24 numbers)."""
    s = digits.strip().zfill(4)
    if len(s) != 4 or len(set(s)) != 4:
        raise ValueError("i-box backtest requires 4 distinct digits")
    return {"".join(p) for p in permutations(s, 4)}


def run_ibox_backtest(
    number: str = "1347",
    operator: str = "Magnum 4D",
    csv_path: Path | None = None,
) -> dict:
    """
    Backtest: bet RM1 on `number` as i-box every draw (Magnum 4D).
    Returns dict with total_cost, total_winnings, profit, n_draws, hits by tier.
    """
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = load_history(str(path))
    if operator is not None:
        df = df.filter(pl.col("operator") == operator)
    if df.height == 0:
        return {"error": f"No draws for {operator or 'all operators'}"}

    draws = get_draws_with_prizes(df)
    box = ibox_permutations(number)

    n_draws = len(draws)
    cost_rm = n_draws * 1.0

    total_winnings = 0.0
    hits_1st = hits_2nd = hits_3rd = hits_special = hits_consolation = 0

    for d in draws:
        w = 0.0
        if d.get("1st") and d["1st"] in box:
            w += IBOX_PRIZE_1ST
            hits_1st += 1
        if d.get("2nd") and d["2nd"] in box:
            w += IBOX_PRIZE_2ND
            hits_2nd += 1
        if d.get("3rd") and d["3rd"] in box:
            w += IBOX_PRIZE_3RD
            hits_3rd += 1
        for n in d.get("special") or []:
            if n in box:
                w += IBOX_PRIZE_SPECIAL
                hits_special += 1
        for n in d.get("consolation") or []:
            if n in box:
                w += IBOX_PRIZE_CONSOLATION
                hits_consolation += 1
        total_winnings += w

    profit = total_winnings - cost_rm
    # Count draws with at least one hit
    draws_with_hit = 0
    for d in draws:
        if d.get("1st") and d["1st"] in box:
            draws_with_hit += 1
            continue
        if d.get("2nd") and d["2nd"] in box:
            draws_with_hit += 1
            continue
        if d.get("3rd") and d["3rd"] in box:
            draws_with_hit += 1
            continue
        for n in d.get("special") or []:
            if n in box:
                draws_with_hit += 1
                break
        else:
            for n in d.get("consolation") or []:
                if n in box:
                    draws_with_hit += 1
                    break

    return {
        "number": number,
        "operator": operator,
        "n_draws": n_draws,
        "cost_rm": cost_rm,
        "total_winnings_rm": total_winnings,
        "profit_rm": profit,
        "hits_1st": hits_1st,
        "hits_2nd": hits_2nd,
        "hits_3rd": hits_3rd,
        "hits_special": hits_special,
        "hits_consolation": hits_consolation,
        "draws_with_hit": draws_with_hit,
    }


def _winnings_for_draws(
    draws: list[dict],
    box: set[str],
    *,
    use_straight_prizes: bool = False,
) -> tuple[float, int, int, int, int, int]:
    """Return (total_winnings, hits_1st, hits_2nd, hits_3rd, hits_special, hits_consolation)."""
    if use_straight_prizes:
        p1, p2, p3, ps, pc = (
            MAGNUM_PRIZE_1ST,
            MAGNUM_PRIZE_2ND,
            MAGNUM_PRIZE_3RD,
            MAGNUM_PRIZE_SPECIAL,
            MAGNUM_PRIZE_CONSOLATION,
        )
    else:
        p1, p2, p3, ps, pc = (
            IBOX_PRIZE_1ST,
            IBOX_PRIZE_2ND,
            IBOX_PRIZE_3RD,
            IBOX_PRIZE_SPECIAL,
            IBOX_PRIZE_CONSOLATION,
        )
    total = 0.0
    h1 = h2 = h3 = hs = hc = 0
    for d in draws:
        if d.get("1st") and d["1st"] in box:
            total += p1
            h1 += 1
        if d.get("2nd") and d["2nd"] in box:
            total += p2
            h2 += 1
        if d.get("3rd") and d["3rd"] in box:
            total += p3
            h3 += 1
        for n in d.get("special") or []:
            if n in box:
                total += ps
                hs += 1
        for n in d.get("consolation") or []:
            if n in box:
                total += pc
                hc += 1
    return (total, h1, h2, h3, hs, hc)


def run_backtest_by_year(
    number: str = "1347",
    operator: str = "Magnum 4D",
    combo: bool = False,
    csv_path: Path | None = None,
) -> list[dict]:
    """
    Backtest by year. Returns list of {year, n_draws, cost_rm, total_winnings_rm, profit_rm}.
    """
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = load_history(str(path))
    if operator is not None:
        df = df.filter(pl.col("operator") == operator)
    if df.height == 0:
        return []

    draws = get_draws_with_prizes(df)
    years = df[DATE_COL].dt.year().to_list()
    by_year: dict[int, list[dict]] = defaultdict(list)
    for y, d in zip(years, draws):
        by_year[y].append(d)

    box = ibox_permutations(number)
    cost_per_draw = STRAIGHT_COST_PER_DRAW if combo else 1.0
    use_straight = combo

    out = []
    for year in sorted(by_year.keys()):
        draws_y = by_year[year]
        n = len(draws_y)
        cost_rm = n * cost_per_draw
        winnings, _, _, _, _, _ = _winnings_for_draws(draws_y, box, use_straight_prizes=use_straight)
        profit_rm = winnings - cost_rm
        out.append({
            "year": year,
            "n_draws": n,
            "cost_rm": cost_rm,
            "total_winnings_rm": winnings,
            "profit_rm": profit_rm,
        })
    return out


def find_best_multisets(
    operator: str | None = None,
    csv_path: Path | None = None,
    top_n: int = 15,
) -> list[dict]:
    """
    Scan all 210 all-different multisets (4 distinct digits). For each, compute
    straight (RM24/draw) backtest total profit and number of profit years (all operators or one).
    Returns list of {key, total_profit_rm, n_profit_years, n_years, recent_5y_profit} sorted by total profit desc.
    """
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = load_history(str(path))
    if operator is not None:
        df = df.filter(pl.col("operator") == operator)
    if df.height == 0:
        return []

    draws = get_draws_with_prizes(df)
    years_list = df[DATE_COL].dt.year().to_list()
    by_year: dict[int, list[dict]] = defaultdict(list)
    for y, d in zip(years_list, draws):
        by_year[y].append(d)

    all_diff_keys = ["".join(str(d) for d in c) for c in combinations(range(10), 4)]
    cost_per_draw = STRAIGHT_COST_PER_DRAW
    results = []

    for key in all_diff_keys:
        box = ibox_permutations(key)
        total_profit = 0.0
        n_profit_years = 0
        year_profits = []
        sorted_years = sorted(by_year.keys())
        for year in sorted_years:
            draws_y = by_year[year]
            n = len(draws_y)
            cost_rm = n * cost_per_draw
            winnings, _, _, _, _, _ = _winnings_for_draws(draws_y, box, use_straight_prizes=True)
            profit_rm = winnings - cost_rm
            total_profit += profit_rm
            if profit_rm > 0:
                n_profit_years += 1
            year_profits.append((year, profit_rm))
        recent_5y = sum(p for _, p in year_profits[-5:]) if len(year_profits) >= 5 else None
        results.append({
            "key": key,
            "total_profit_rm": total_profit,
            "n_profit_years": n_profit_years,
            "n_years": len(sorted_years),
            "recent_5y_profit": recent_5y,
        })
    results.sort(key=lambda x: -x["total_profit_rm"])
    return results[:top_n]


def run_combo_backtest(
    number: str = "1347",
    operator: str = "Magnum 4D",
    csv_path: Path | None = None,
) -> dict:
    """
    Backtest: bet RM1 on each of the 24 straight numbers (combos) every draw.
    Cost = RM24 per draw. Prizes: 1st 2500, 2nd 1000, 3rd 500, Special 180, Consolation 60.
    """
    path = csv_path or DEFAULT_CSV
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = load_history(str(path))
    if operator is not None:
        df = df.filter(pl.col("operator") == operator)
    if df.height == 0:
        return {"error": f"No draws for {operator or 'all operators'}"}

    draws = get_draws_with_prizes(df)
    box = ibox_permutations(number)

    n_draws = len(draws)
    cost_rm = n_draws * STRAIGHT_COST_PER_DRAW

    total_winnings = 0.0
    hits_1st = hits_2nd = hits_3rd = hits_special = hits_consolation = 0

    for d in draws:
        w = 0.0
        if d.get("1st") and d["1st"] in box:
            w += MAGNUM_PRIZE_1ST
            hits_1st += 1
        if d.get("2nd") and d["2nd"] in box:
            w += MAGNUM_PRIZE_2ND
            hits_2nd += 1
        if d.get("3rd") and d["3rd"] in box:
            w += MAGNUM_PRIZE_3RD
            hits_3rd += 1
        for n in d.get("special") or []:
            if n in box:
                w += MAGNUM_PRIZE_SPECIAL
                hits_special += 1
        for n in d.get("consolation") or []:
            if n in box:
                w += MAGNUM_PRIZE_CONSOLATION
                hits_consolation += 1
        total_winnings += w

    profit = total_winnings - cost_rm
    draws_with_hit = 0
    for d in draws:
        if d.get("1st") and d["1st"] in box:
            draws_with_hit += 1
            continue
        if d.get("2nd") and d["2nd"] in box:
            draws_with_hit += 1
            continue
        if d.get("3rd") and d["3rd"] in box:
            draws_with_hit += 1
            continue
        for n in d.get("special") or []:
            if n in box:
                draws_with_hit += 1
                break
        else:
            for n in d.get("consolation") or []:
                if n in box:
                    draws_with_hit += 1
                    break

    return {
        "number": number,
        "operator": operator,
        "n_draws": n_draws,
        "cost_rm": cost_rm,
        "total_winnings_rm": total_winnings,
        "profit_rm": profit,
        "hits_1st": hits_1st,
        "hits_2nd": hits_2nd,
        "hits_3rd": hits_3rd,
        "hits_special": hits_special,
        "hits_consolation": hits_consolation,
        "draws_with_hit": draws_with_hit,
    }


def _main_find_best(console, args) -> None:
    from rich.panel import Panel
    from rich.table import Table

    op_label = "All operators" if args.operator is None else args.operator
    console.print(Panel(f"[bold]Find best multisets (straight RM24/draw) — {op_label}[/]", border_style="cyan"))
    try:
        best = find_best_multisets(operator=args.operator, top_n=20)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        return
    if not best:
        console.print("[yellow]No data.[/]")
        return

    t = Table(show_header=True, header_style="bold", title="Top 20 by total P&L")
    t.add_column("Rank", justify="right")
    t.add_column("Number", style="dim")
    t.add_column("Total P&L (RM)", justify="right")
    t.add_column("Profit years", justify="right")
    t.add_column("Recent 5y P&L", justify="right")
    for i, r in enumerate(best, 1):
        rec = r.get("recent_5y_profit")
        rec_str = f"{rec:+,.0f}" if rec is not None else "—"
        t.add_row(str(i), r["key"], f"{r['total_profit_rm']:+,.0f}", str(r["n_profit_years"]), rec_str)
    console.print(t)
    console.print()
    best_total = best[0]
    by_years = sorted(best, key=lambda x: -x["n_profit_years"])
    best_years = by_years[0]
    console.print(f"  [bold]Best by total P&L:[/] [green]{best_total['key']}[/] (RM {best_total['total_profit_rm']:+,.0f}, {best_total['n_profit_years']} profit years)")
    console.print(f"  [bold]Best by profit-year count:[/] [green]{best_years['key']}[/] ({best_years['n_profit_years']} profit years, RM {best_years['total_profit_rm']:+,.0f} total)")
    if best_total["total_profit_rm"] <= 0:
        console.print("  [dim]No multiset has total profit > 0 over full history (house edge).[/]")


def _main_by_year(console, args) -> None:
    from rich.panel import Panel
    from rich.table import Table

    if args.all_over:
        if args.operator is None:
            from analysis.pattern_analysis import get_top_over_multisets
            numbers = get_top_over_multisets(operator=None, n=5)
            if not numbers:
                numbers = TOP_OVER_MULTISETS_MAGNUM
        else:
            numbers = TOP_OVER_MULTISETS_MAGNUM
    else:
        numbers = [args.number]
    mode_label = "straight (RM1×24/draw)"
    op_label = "All operators" if args.operator is None else args.operator
    console.print(Panel(f"[bold]Backtest by year — {mode_label} — {op_label}[/]", border_style="cyan"))

    number_totals = []
    for num in numbers:
        try:
            rows = run_backtest_by_year(number=num, operator=args.operator, combo=True)
            total = sum(r["profit_rm"] for r in rows) if rows else 0
            number_totals.append((num, total, rows))
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/]")
            return
    if args.all_over and len(number_totals) > 1:
        number_totals.sort(key=lambda x: x[1], reverse=True)

    for num, _total_profit, rows in number_totals:
        if not rows:
            continue

        years_profit = sum(1 for r in rows if r["profit_rm"] > 0)
        years_loss = sum(1 for r in rows if r["profit_rm"] < 0)
        years_even = sum(1 for r in rows if r["profit_rm"] == 0)

        console.print(f"\n[bold]{num}[/] ({mode_label})")
        t = Table(show_header=True, header_style="bold")
        t.add_column("Year", justify="right")
        t.add_column("Draws", justify="right")
        t.add_column("Cost (RM)", justify="right")
        t.add_column("Winnings (RM)", justify="right")
        t.add_column("Profit/Loss (RM)", justify="right")
        for r in rows:
            style = "green" if r["profit_rm"] > 0 else "red" if r["profit_rm"] < 0 else "dim"
            t.add_row(
                str(r["year"]),
                str(r["n_draws"]),
                f"{r['cost_rm']:,.0f}",
                f"{r['total_winnings_rm']:,.0f}",
                f"[{style}]{r['profit_rm']:+,.0f}[/]",
            )
        console.print(t)
        console.print(
            f"  Summary: [green]{years_profit} years profit[/], "
            f"[red]{years_loss} years loss[/]"
            + (f", [dim]{years_even} even[/]" if years_even else "")
        )


def main() -> None:
    import argparse

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    parser = argparse.ArgumentParser(description="i-box or combo (24 straight) backtest")
    parser.add_argument("--number", type=str, default="1347", help="4 distinct digits (e.g. 1347)")
    parser.add_argument("--all-over", action="store_true", help="Run for all top-over multisets (1347, 5789, 0178, 2358, 1248)")
    parser.add_argument("--combo", action="store_true", help="Bet RM1 on each of 24 combos (RM24/draw) instead of i-box (RM1/draw)")
    parser.add_argument("--by-year", action="store_true", help="By year for straight (combo) only; show years profit vs loss")
    parser.add_argument("--find-best", action="store_true", help="Scan all 210 all-different multisets; report best by total P&L and by profit years")
    parser.add_argument("--operator", type=str, default="Magnum 4D", help="Operator filter (default Magnum 4D)")
    parser.add_argument("--all-operators", action="store_true", help="Include all operators (Magnum, Sports Toto, Da Ma Cai)")
    args = parser.parse_args()

    console = Console()
    if args.all_operators:
        args.operator = None

    if args.find_best:
        _main_find_best(console, args)
        return

    # When all-operators + all-over, use top-over multisets from combined data (not Magnum-only)
    if args.all_over:
        if args.operator is None:
            from analysis.pattern_analysis import get_top_over_multisets
            numbers_all_over = get_top_over_multisets(operator=None, n=5)
            if not numbers_all_over:
                numbers_all_over = TOP_OVER_MULTISETS_MAGNUM  # fallback
        else:
            numbers_all_over = TOP_OVER_MULTISETS_MAGNUM

    run_fn = run_combo_backtest if args.combo else run_ibox_backtest
    mode_label = "combo (RM1×24 per draw)" if args.combo else "i-box (RM1 per draw)"
    op_label = "All operators" if args.operator is None else args.operator

    if args.by_year:
        # By-year is straight (combo) only
        args.combo = True
        _main_by_year(console, args)
        return

    if args.all_over:
        numbers = numbers_all_over
        console.print(Panel(f"[bold]{mode_label} backtest: top-over multisets ({op_label}) — {numbers}[/]", border_style="cyan"))
    else:
        numbers = [args.number]
        console.print(Panel(f"[bold]{mode_label} backtest: {args.number} ({args.operator})[/]", border_style="cyan"))

    results = []
    for num in numbers:
        try:
            res = run_fn(number=num, operator=args.operator)
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/]")
            sys.exit(1)
        if res.get("error"):
            console.print(f"[red]{res['error']}[/]")
            sys.exit(1)
        results.append(res)

    if len(results) == 1:
        res = results[0]
        per_draw = STRAIGHT_COST_PER_DRAW if args.combo else 1.0
        console.print(f"  Number: {res['number']} (24 permutations, all-different)")
        console.print(f"  Operator: {res['operator']}")
        console.print(f"  Draws: {res['n_draws']}  |  Cost per draw: RM {per_draw:,.0f}")
        console.print()
        t = Table(show_header=True, header_style="bold")
        t.add_column("Metric", style="dim")
        t.add_column("Value", justify="right")
        cost_desc = "Total cost (RM24 × draws)" if args.combo else "Total cost (RM1 × draws)"
        t.add_row(cost_desc, f"RM {res['cost_rm']:,.2f}")
        t.add_row("Total winnings", f"RM {res['total_winnings_rm']:,.2f}")
        t.add_row("Profit / Loss", f"RM {res['profit_rm']:+,.2f}")
        t.add_row("Draws with at least one hit", str(res["draws_with_hit"]))
        console.print(t)
        console.print()
        console.print("[bold]Hits by tier[/]")
        console.print(f"  1st: {res['hits_1st']}  |  2nd: {res['hits_2nd']}  |  3rd: {res['hits_3rd']}  |  Special: {res['hits_special']}  |  Consolation: {res['hits_consolation']}")
        console.print()
        if res["profit_rm"] >= 0:
            console.print("[green]Result: Profit[/]")
        else:
            console.print("[red]Result: Loss[/]")
        return

    # Table for multiple numbers
    title = "Top-over multisets combo backtest (RM1×24 per draw)" if args.combo else "Top-over multisets i-box backtest (RM1 per draw)"
    t = Table(show_header=True, header_style="bold", title=title)
    t.add_column("Number", style="dim")
    t.add_column("Cost (RM)", justify="right")
    t.add_column("Winnings (RM)", justify="right")
    t.add_column("Profit/Loss (RM)", justify="right")
    t.add_column("Draws hit", justify="right")
    t.add_column("1st", justify="right")
    t.add_column("2nd", justify="right")
    t.add_column("3rd", justify="right")
    t.add_column("Spec", justify="right")
    t.add_column("Cons", justify="right")
    for res in results:
        profit = res["profit_rm"]
        style = "green" if profit >= 0 else "red"
        t.add_row(
            res["number"],
            f"{res['cost_rm']:,.0f}",
            f"{res['total_winnings_rm']:,.0f}",
            f"[{style}]{profit:+,.0f}[/]",
            str(res["draws_with_hit"]),
            str(res["hits_1st"]),
            str(res["hits_2nd"]),
            str(res["hits_3rd"]),
            str(res["hits_special"]),
            str(res["hits_consolation"]),
        )
    console.print(t)
    console.print()
    results_sorted = sorted(results, key=lambda r: r["profit_rm"], reverse=True)
    best = results_sorted[0]
    worst = results_sorted[-1]
    console.print(f"  [bold]Top (best P&L):[/] [green]{best['number']}[/] (RM {best['profit_rm']:+,.2f})")
    console.print(f"  Worst P&L: [red]{worst['number']}[/] (RM {worst['profit_rm']:+,.2f})")


if __name__ == "__main__":
    main()
