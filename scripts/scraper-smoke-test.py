#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper import scrape_past_date  # noqa: E402


EXPECTED_OPERATORS = ["Magnum 4D", "Da Ma Cai 1+3D", "Sports Toto 4D"]


def _assert_condition(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def validate_draws(draws: list[dict[str, Any]], source: str, date_str: str) -> None:
    by_op = {d.get("draw_name"): d for d in draws}

    for op in EXPECTED_OPERATORS:
        _assert_condition(op in by_op, f"[{source}] Missing operator {op} for {date_str}")

        d = by_op[op]
        _assert_condition(d.get("draw_no"), f"[{source}] Missing draw_no for {op} {date_str}")
        _assert_condition(d.get("first_prize"), f"[{source}] Missing 1st prize for {op} {date_str}")
        _assert_condition(d.get("second_prize"), f"[{source}] Missing 2nd prize for {op} {date_str}")
        _assert_condition(d.get("third_prize"), f"[{source}] Missing 3rd prize for {op} {date_str}")

        special = d.get("special") or []
        consolation = d.get("consolation") or []
        _assert_condition(isinstance(special, list), f"[{source}] special not a list for {op} {date_str}")
        _assert_condition(isinstance(consolation, list), f"[{source}] consolation not a list for {op} {date_str}")
        _assert_condition(len(special) > 0, f"[{source}] Empty special for {op} {date_str}")
        _assert_condition(len(consolation) > 0, f"[{source}] Empty consolation for {op} {date_str}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate scraper adapters for past 4D results.")
    parser.add_argument("--date", default="2026-03-18", help="Date as YYYY-MM-DD (default: 2026-03-18)")
    parser.add_argument("--sources", default="4dmy,4dkingdom", help="Comma-separated sources to validate.")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    ok = True
    for src in sources:
        try:
            draws = scrape_past_date(args.date, sources=[src])
            validate_draws(draws, src, args.date)
            print(f"[OK] {src}: {len(draws)} draw(s) parsed for {args.date}")
        except Exception as exc:
            ok = False
            print(f"[FAIL] {src}: {exc}", file=sys.stderr)

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

