#!/usr/bin/env python3
"""
Incremental scraper for Magnum 4D, Da Ma Cai 1+3D, and Sports Toto 4D past results.

- Starts from yesterday and goes back one day at a time.
- Skips dates that already exist in the CSV (resumable).
- Writes to a CSV file suitable for Excel.
- Optional: use many workers for parallel fetch, or Rust extension for max speed.

Usage:
  python scrape_history.py [--csv PATH] [--workers N] [--max-days N]
  python scrape_history.py --workers 20     # 20 parallel requests (fast)
  python scrape_history.py --workers 1       # serial with delay (safe)
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from scraper import fetch_past_date, parse_results_html

# Optional Rust extension for parallel HTTP (same API: fetch_past_dates(url, dates) -> list of (date_str, html))
try:
    from fetch_4d import fetch_past_dates as rust_fetch_past_dates

    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False

CSV_COLUMNS = [
    "date",
    "operator",
    "draw_no",
    "1st",
    "2nd",
    "3rd",
    "special",
    "consolation",
]


def normalize_operator_name(draw_name: str) -> str:
    """Map draw_name to a short CSV operator label."""
    if "Magnum 4D" in draw_name:
        return "Magnum 4D"
    if "Da Ma Cai 1+3D" in draw_name or (
        "Da Ma Cai" in draw_name and "1+3D" in draw_name
    ):
        return "Da Ma Cai 1+3D"
    if (
        "SportsToto 4D" in draw_name
        and "5D" not in draw_name
        and "6D" not in draw_name
        and "Lotto" not in draw_name
    ):
        return "Sports Toto 4D"
    return ""


def draw_to_rows(d: dict, date_str: str) -> list[dict]:
    """Convert one draw dict to CSV row(s). One row per draw."""
    operator = normalize_operator_name(d.get("draw_name") or "")
    if not operator:
        return []
    special = d.get("special") or []
    consolation = d.get("consolation") or []
    return [
        {
            "date": date_str,
            "operator": operator,
            "draw_no": (d.get("draw_no") or "").strip(),
            "1st": (d.get("first_prize") or "").strip(),
            "2nd": (d.get("second_prize") or "").strip(),
            "3rd": (d.get("third_prize") or "").strip(),
            "special": ",".join(str(n) for n in special),
            "consolation": ",".join(str(n) for n in consolation),
        }
    ]


def get_existing_dates(csv_path: str) -> set[str]:
    """Read CSV and return set of dates (YYYY-MM-DD) that already have data."""
    existing = set()
    if not os.path.isfile(csv_path):
        return existing
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != CSV_COLUMNS:
            return existing
        for row in reader:
            d = row.get("date", "").strip()
            if d:
                existing.add(d)
    return existing


def append_to_csv(csv_path: str, rows: list[dict], write_header: bool) -> None:
    """Append rows to CSV. write_header=True if file is new or empty."""
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def _fetch_one(date_str: str) -> tuple[str, str | None]:
    """Fetch one date; return (date_str, html or None on error)."""
    try:
        html = fetch_past_date(date_str)
        return (date_str, html)
    except Exception as e:
        print(f"Error fetching {date_str}: {e}", file=sys.stderr)
        return (date_str, None)


def _process_batch_python(
    dates: list[str], workers: int
) -> list[tuple[str, str | None]]:
    """Fetch multiple dates in parallel using ThreadPoolExecutor."""
    results: list[tuple[str, str | None]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_fetch_one, d): d for d in dates}
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


def run(
    csv_path: str = "4d_history.csv",
    delay_seconds: float = 0.0,
    max_days: int | None = None,
    workers: int = 20,
    batch_size: int = 50,
) -> None:
    today = date.today()
    start_date = today - timedelta(days=1)
    existing_dates = get_existing_dates(csv_path)
    file_exists = os.path.isfile(csv_path)
    write_header = not file_exists
    serial = workers <= 1
    if serial and delay_seconds <= 0:
        delay_seconds = 1.0

    base_url = "https://www.check4d.org"
    day_count = 0
    total_saved = 0

    while True:
        if max_days is not None and day_count >= max_days:
            break

        # Collect next batch of missing dates
        batch: list[str] = []
        while len(batch) < batch_size:
            d = start_date - timedelta(days=day_count)
            date_str = d.isoformat()
            if date_str not in existing_dates:
                batch.append(date_str)
            day_count += 1
            if max_days is not None and day_count >= max_days:
                break
            if len(batch) >= batch_size:
                break

        if not batch:
            break

        if serial:
            # One at a time
            for date_str in batch:
                try:
                    html = fetch_past_date(date_str)
                except Exception as e:
                    print(f"Error fetching {date_str}: {e}", file=sys.stderr)
                    existing_dates.add(date_str)
                    time.sleep(delay_seconds)
                    continue
                draws = parse_results_html(html)
                rows = []
                for draw in draws:
                    rows.extend(draw_to_rows(draw, date_str))
                if rows:
                    append_to_csv(csv_path, rows, write_header)
                    write_header = False
                    total_saved += len(rows)
                    print(f"Saved {date_str}: {len(rows)} row(s)")
                else:
                    print(f"Skip {date_str}: no Magnum/Da Ma Cai/Sports Toto 4D draws")
                existing_dates.add(date_str)
                time.sleep(delay_seconds)
            continue

        # Parallel: fetch batch
        if _RUST_AVAILABLE:
            try:
                raw = rust_fetch_past_dates(base_url, batch)
                results = [(d, h) for d, h in raw if h is not None]
            except Exception as e:
                print(f"Rust fetch failed, falling back to Python: {e}", file=sys.stderr)
                results = _process_batch_python(batch, workers)
        else:
            results = _process_batch_python(batch, workers)

        # Sort by date and process
        results.sort(key=lambda x: x[0])
        for date_str, html in results:
            if html is None:
                existing_dates.add(date_str)
                continue
            draws = parse_results_html(html)
            rows = []
            for draw in draws:
                rows.extend(draw_to_rows(draw, date_str))
            if rows:
                append_to_csv(csv_path, rows, write_header)
                write_header = False
                total_saved += len(rows)
                print(f"Saved {date_str}: {len(rows)} row(s)")
            else:
                print(f"Skip {date_str}: no Magnum/Da Ma Cai/Sports Toto 4D draws")
            existing_dates.add(date_str)

    if total_saved:
        print(f"Done. Total rows written this run: {total_saved}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Magnum, Da Ma Cai, Sports Toto 4D history into CSV (incremental, resumable)."
    )
    parser.add_argument(
        "--csv",
        default="4d_history.csv",
        help="Output CSV path (default: 4d_history.csv)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay between requests in serial mode (default: 1.0 when workers=1)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=20,
        help="Parallel fetch workers (default: 20). Use 1 for serial.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Max dates per batch when parallel (default: 50)",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=None,
        help="Stop after this many days (default: no limit)",
    )
    args = parser.parse_args()
    if _RUST_AVAILABLE:
        print("Using Rust extension for fast parallel fetch.", file=sys.stderr)
    run(
        csv_path=args.csv,
        delay_seconds=args.delay,
        max_days=args.max_days,
        workers=args.workers,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
