"""
Simple FastAPI + Jinja app to view 4D strategy data and outcomes.
Run: uvicorn web.main:app --reload
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import date as _date
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from analysis.strategy_24 import (
    get_precomputed_winnings,
    run_best_multiset_backtest,
    run_top24_individual_backtest,
)
import polars as pl

from analysis.load import load_history, DEFAULT_CSV
from scrape_history import run as scrape_history_run

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CSV_PATH = Path(os.environ.get("4D_HISTORY_CSV", str(DEFAULT_CSV)))

app = FastAPI(title="4D Strategy", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "web" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "web" / "templates")

scheduler = AsyncIOScheduler()


def _compute_backfill_days(csv_path: str) -> int:
    """
    Determine how many days to backfill based on the last date in the CSV.
    Always covers from last known draw date up to yesterday, with a small buffer.
    """
    try:
        df = load_history(csv_path)
    except FileNotFoundError:
        # If file is missing, fall back to a conservative window.
        logger.warning("CSV {} not found when computing backfill days; using 30 days", csv_path)
        return 30
    if "date" not in df.columns or df.height == 0:
        logger.warning("CSV {} has no date column or is empty; using 30 days", csv_path)
        return 30
    last_date = df["date"].max()
    if not isinstance(last_date, _date):
        try:
            last_date = _date.fromisoformat(str(last_date))
        except Exception:
            logger.warning("Unable to parse last date {!r} from CSV {}; using 30 days", last_date, csv_path)
            return 30
    today = _date.today()
    days_since_last = max(0, (today - last_date).days)
    # Ensure we at least cover a small recent window even if CSV is very fresh.
    max_days = max(days_since_last + 2, 7)
    return max_days


async def _run_scraper_job() -> None:
    """
    Scheduled job: keep 4d_history.csv up to date for the recent days.
    Runs scrape_history.run in a thread so it doesn't block the event loop.
    """
    csv_path = str(CSV_PATH)
    max_days = _compute_backfill_days(csv_path)
    logger.info("Scraper job starting for CSV path {} with max_days={}", csv_path, max_days)
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None,
            lambda: scrape_history_run(
                csv_path=csv_path,
                delay_seconds=0.0,
                max_days=max_days,
                workers=20,
                batch_size=50,
            ),
        )
        logger.info("Scraper job completed for CSV path {}", csv_path)
    except Exception as exc:
        logger.exception("Scraper job failed: {}", exc)


@app.on_event("startup")
async def _start_scheduler() -> None:
    """
    Start APScheduler when FastAPI starts.
    Default: run scraper multiple times after typical draw time.
    4D draws usually finish and publish results around 7:00–8:00 PM MYT.
    We run at 20:30, 21:00, and 21:30 to give buffer for upstream delays.
    """
    if scheduler.running:
        return

    # Kick off one run shortly after startup to backfill recent days.
    logger.info("Scheduling immediate scraper job after startup")
    asyncio.create_task(_run_scraper_job())

    # Run three times every evening (server local time) after typical draw time.
    for job_id, hour, minute in [
        ("scrape_history_2030", 20, 30),
        ("scrape_history_2100", 21, 0),
        ("scrape_history_2130", 21, 30),
    ]:
        scheduler.add_job(
            _run_scraper_job,
            CronTrigger(hour=hour, minute=minute),
            id=job_id,
            replace_existing=True,
        )
        logger.info("Scheduled scraper job {} at {:02d}:{:02d}", job_id, hour, minute)

    logger.info("Starting APScheduler")
    scheduler.start()


@app.on_event("shutdown")
async def _shutdown_scheduler() -> None:
    """Shutdown APScheduler gracefully when FastAPI stops."""
    if scheduler.running:
        scheduler.shutdown(wait=False)


def _get_operators():
    if not CSV_PATH.is_file():
        return []
    df = load_history(str(CSV_PATH))
    return df["operator"].unique().sort().to_list()


def _get_date_range():
    """Return (min_date_str, max_date_str) from CSV for form defaults, or (None, None)."""
    if not CSV_PATH.is_file():
        return None, None
    df = load_history(str(CSV_PATH))
    if "date" not in df.columns or df.height == 0:
        return None, None
    min_d = df["date"].min()
    max_d = df["date"].max()
    return (min_d.isoformat() if min_d else None, max_d.isoformat() if max_d else None)


def _get_all_data(
    start_date: str | None = None,
    end_date: str | None = None,
    n: int = 24,
    bet_types: tuple[str, ...] | None = None,
) -> dict | None:
    """Compute strategy data for all operators and per-operator. Returns dict for templates."""
    if not CSV_PATH.is_file():
        return None
    n = max(1, min(n, 1000))
    data = {"has_data": True, "operators": [], "all_operators": None}
    operators = _get_operators()
    for op in operators:
        op_str = str(op)
        try:
            w, n_draws = get_precomputed_winnings(
                operator=op_str,
                csv_path=CSV_PATH,
                progress=False,
                date_min=start_date,
                date_max=end_date,
                bet_types=bet_types,
            )
            top_n_list, res = run_top24_individual_backtest(
                _winnings=w, _n_draws=n_draws, n=n, bet_types=bet_types
            )
            best_ms, best_nums, ms_res = run_best_multiset_backtest(
                _winnings=w, _n_draws=n_draws, progress=False
            )
            data["operators"].append({
                "name": op_str,
                "draws": n_draws,
                "top24": sorted(top_n_list),
                "top24_profit": res["profit_rm"],
                "top24_profit_fmt": f"{res['profit_rm']:+,.0f}",
                "top24_winnings": res["total_winnings_rm"],
                "top24_winnings_fmt": f"{res['total_winnings_rm']:,.0f}",
                "top24_cost": res["cost_rm"],
                "top24_cost_fmt": f"{res['cost_rm']:,.0f}",
                "best_multiset": best_ms,
                "multiset_numbers": sorted(best_nums) if best_nums else [],
                "multiset_profit": ms_res["profit_rm"],
                "multiset_profit_fmt": f"{ms_res['profit_rm']:+,.0f}",
                "multiset_winnings": ms_res["total_winnings_rm"],
                "multiset_winnings_fmt": f"{ms_res['total_winnings_rm']:,.0f}",
            })
        except Exception as e:
            data["operators"].append({"name": op_str, "error": str(e)})
    try:
        w, n_draws = get_precomputed_winnings(
            operator=None,
            csv_path=CSV_PATH,
            progress=False,
            date_min=start_date,
            date_max=end_date,
            bet_types=bet_types,
        )
        top_n_list, res = run_top24_individual_backtest(
            _winnings=w, _n_draws=n_draws, n=n, bet_types=bet_types
        )
        best_ms, best_nums, ms_res = run_best_multiset_backtest(
            _winnings=w, _n_draws=n_draws, progress=False
        )
        data["all_operators"] = {
            "draws": n_draws,
            "top24": sorted(top_n_list),
            "top24_profit": res["profit_rm"],
            "top24_profit_fmt": f"{res['profit_rm']:+,.0f}",
            "top24_winnings_fmt": f"{res['total_winnings_rm']:,.0f}",
            "top24_cost_fmt": f"{res['cost_rm']:,.0f}",
            "best_multiset": best_ms,
            "multiset_numbers": sorted(best_nums) if best_nums else [],
            "multiset_profit": ms_res["profit_rm"],
            "multiset_profit_fmt": f"{ms_res['profit_rm']:+,.0f}",
            "multiset_winnings_fmt": f"{ms_res['total_winnings_rm']:,.0f}",
            "multiset_cost_fmt": f"{ms_res['cost_rm']:,.0f}",
        }
    except Exception as e:
        data["all_operators"] = {"error": str(e)}
    return data


def _norm(s: str) -> str:
    return str(s).strip().zfill(4)


def _get_chart_data(
    top_numbers: list[str],
    start_date: str | None,
    end_date: str | None,
    operator: str | list[str] | None = None,
) -> dict | None:
    """
    For each top number, count wins per month in the date range.
    operator: if set (str or list of str), only count wins from those operators; otherwise all.
    Returns { "labels": [...], "datasets": [...], "totals": {...} }.
    """
    if not CSV_PATH.is_file() or not top_numbers:
        return None
    df = load_history(str(CSV_PATH))
    if "date" not in df.columns or df.height == 0:
        return None
    if operator is not None:
        if isinstance(operator, list):
            if operator:
                op_list = [o.strip() for o in operator if o and str(o).strip()]
                if op_list:
                    df = df.filter(pl.col("operator").is_in(op_list))
        elif operator.strip():
            df = df.filter(pl.col("operator") == operator.strip())
    if start_date:
        dmin = _date.fromisoformat(start_date)
        df = df.filter(pl.col("date") >= pl.lit(dmin))
    if end_date:
        dmax = _date.fromisoformat(end_date)
        df = df.filter(pl.col("date") <= pl.lit(dmax))
    if df.height == 0:
        return None
    top_set = {_norm(n) for n in top_numbers}
    # (number -> month -> count)
    by_number_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    months_seen: set[str] = set()
    prize_cols = ["1st", "2nd", "3rd", "special", "consolation"]
    for row in df.iter_rows(named=True):
        d = row.get("date")
        month_key = d.strftime("%Y-%m") if hasattr(d, "strftime") else str(d)[:7]
        months_seen.add(month_key)
        winners = []
        for col in ["1st", "2nd", "3rd"]:
            v = row.get(col)
            if v is not None and str(v).strip():
                winners.append(_norm(str(v)))
        for col in ["special", "consolation"]:
            v = row.get(col)
            if v is not None and v:
                for part in str(v).split(","):
                    if part and part.strip():
                        winners.append(_norm(part.strip()))
        for num in winners:
            if num in top_set:
                by_number_month[num][month_key] += 1
    months_sorted = sorted(months_seen)
    # Total wins per number (all top_numbers)
    totals = {num: sum(by_number_month[_norm(num)].values()) for num in top_numbers}
    # Limit to 30 numbers, sorted by total count descending so legend matches
    numbers_for_chart = sorted(top_numbers[:30], key=lambda num: -totals.get(num, 0))
    datasets = []
    for num in numbers_for_chart:
        n = _norm(num)
        counts = [by_number_month[n].get(m, 0) for m in months_sorted]
        datasets.append({"number": n, "counts": counts})
    return {"labels": months_sorted, "datasets": datasets, "totals": totals}


def _chart_top_numbers_for_operators(
    data: dict,
    chart_operators: list[str],
    start_date: str | None,
    end_date: str | None,
    n: int,
) -> list[str]:
    """Resolve which top N list to use for the chart.
    chart_operators: empty = all, one = that op's top N, many = union of each op's top N."""
    all_op_top = data["all_operators"]["top24"]
    if not chart_operators:
        return all_op_top
    if len(chart_operators) == 1:
        want = (chart_operators[0] or "").strip()
        for op in data.get("operators") or []:
            name = (op.get("name") or "").strip()
            if name == want and "top24" in op:
                return op["top24"]
        return all_op_top
    # Multiple operators: union of each operator's top N (so chart includes both sets)
    seen: set[str] = set()
    result: list[str] = []
    for want in chart_operators:
        want = (want or "").strip()
        if not want:
            continue
        for op in data.get("operators") or []:
            name = (op.get("name") or "").strip()
            if name == want and "top24" in op:
                for num in op["top24"]:
                    nnorm = (num or "").strip()
                    if nnorm and nnorm not in seen:
                        seen.add(nnorm)
                        result.append(num)
                break
    return result if result else all_op_top


def _get_chart_api_payload(
    start_date: str | None,
    end_date: str | None,
    n: int,
    chart_operators: list[str] | None,
) -> dict | None:
    """Build chart data for API: { labels, datasets } (no totals). Returns None if no data."""
    data = _get_all_data(start_date=start_date, end_date=end_date, n=n)
    if not data or not data.get("has_data") or not data.get("all_operators") or data["all_operators"].get("error"):
        return None
    op_list = [o for o in (chart_operators or []) if o and str(o).strip()]
    chart_top_numbers = _chart_top_numbers_for_operators(data, op_list, start_date, end_date, n)
    operator_filter = op_list if op_list else None
    chart_data = _get_chart_data(
        chart_top_numbers,
        start_date=start_date or None,
        end_date=end_date or None,
        operator=operator_filter,
    )
    if not chart_data or "datasets" not in chart_data:
        return None
    filter_label = ", ".join(op_list) if op_list else "All operators"
    return {
        "labels": chart_data["labels"],
        "datasets": chart_data["datasets"],
        "filter_label": filter_label,
    }


# ── API: draw results (latest/draws-by-date) ──────────────────────────────────────────

def _norm_prize(value: object) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    return _norm(s)


def _split_prize_list(value: object) -> list[str]:
    if value is None:
        return []
    s = str(value).strip()
    if not s:
        return []
    parts = [p.strip() for p in s.split(",") if p and p.strip()]
    return [_norm(p) for p in parts]


def _serialize_latest_draw_row(row: dict) -> dict:
    d = row.get("date")
    date_str = d.isoformat() if hasattr(d, "isoformat") else str(d)
    return {
        "date": date_str,
        "operator": str(row.get("operator") or ""),
        "draw_no": str(row.get("draw_no") or ""),
        "1st": _norm_prize(row.get("1st")),
        "2nd": _norm_prize(row.get("2nd")),
        "3rd": _norm_prize(row.get("3rd")),
        "special": _split_prize_list(row.get("special")),
        "consolation": _split_prize_list(row.get("consolation")),
    }


def _get_latest_draws_per_operator() -> list[dict]:
    if not CSV_PATH.is_file():
        return []
    df = load_history(str(CSV_PATH)).select(
        ["date", "operator", "draw_no", "1st", "2nd", "3rd", "special", "consolation"]
    )
    # Pick the latest draw_no for each operator on the latest date.
    df = df.sort(["operator", "date", "draw_no"])
    latest = df.group_by("operator").tail(1)
    return [_serialize_latest_draw_row(r) for r in latest.iter_rows(named=True)]


def _get_draw_dates() -> list[str]:
    if not CSV_PATH.is_file():
        return []
    df = load_history(str(CSV_PATH)).select(["date"]).unique().sort("date", descending=True)
    out: list[str] = []
    for d in df["date"].to_list():
        out.append(d.isoformat() if hasattr(d, "isoformat") else str(d))
    return out


def _get_draws_for_date(date_str: str) -> list[dict]:
    if not CSV_PATH.is_file():
        return []
    try:
        dmin = _date.fromisoformat(date_str)
    except Exception:
        return []
    df = load_history(str(CSV_PATH)).select(
        ["date", "operator", "draw_no", "1st", "2nd", "3rd", "special", "consolation"]
    )
    day_rows = df.filter(pl.col("date") == pl.lit(dmin))
    if day_rows.height == 0:
        return []
    day_rows = day_rows.sort(["operator", "draw_no"]).group_by("operator").tail(1)
    return [_serialize_latest_draw_row(r) for r in day_rows.iter_rows(named=True)]


def _parse_bet_types(request: Request) -> tuple[str, ...]:
    q = request.query_params

    def _truthy(key: str) -> bool:
        v = q.get(key)
        return v is not None and str(v).strip().lower() not in ("0", "false", "no", "off", "")

    bet_types: list[str] = []
    if _truthy("bet_4d_big"):
        bet_types.append("4d_big")
    if _truthy("bet_4d_small"):
        bet_types.append("4d_small")
    if _truthy("bet_3d_big"):
        bet_types.append("3d_big")
    if _truthy("bet_3d_small"):
        bet_types.append("3d_small")

    # Strategy defaults (legacy): 4D Big + 3D Big.
    if not bet_types:
        return ("4d_big", "3d_big")
    return tuple(bet_types)


@app.get("/latest-draws")
@app.get("/api/latest-draws")
async def api_latest_draws():
    """Return the latest draw result per operator (for Results page)."""
    draws = _get_latest_draws_per_operator()
    return JSONResponse(content={"draws": draws})


@app.get("/draw-dates")
@app.get("/api/draw-dates")
async def api_draw_dates():
    """Return list of dates that have draws (YYYY-MM-DD), sorted descending (most recent first)."""
    dates = _get_draw_dates()
    return JSONResponse(content={"dates": dates})


@app.get("/draws")
@app.get("/api/draws")
async def api_draws_for_date(request: Request):
    """Return draws for a specific date (query param date=YYYY-MM-DD)."""
    date_param = request.query_params.get("date")
    if not date_param:
        return JSONResponse(content={"draws": []})
    draws = _get_draws_for_date(date_param.strip())
    return JSONResponse(content={"draws": draws})


@app.get("/data")
@app.get("/api/data")
async def api_data(request: Request):
    """Return full dashboard data as JSON for the SPA."""
    q = request.query_params
    start_date = q.get("start_date")
    end_date = q.get("end_date")
    n_val = q.get("n")

    n = 24
    if n_val is not None:
        try:
            n = max(1, min(int(n_val), 1000))
        except ValueError:
            n = 24

    date_min_csv, date_max_csv = _get_date_range()
    start_date = start_date or date_min_csv
    end_date = end_date or date_max_csv
    bet_types = _parse_bet_types(request)

    data = _get_all_data(start_date=start_date, end_date=end_date, n=n, bet_types=bet_types)
    operators = _get_operators()

    top_numbers_with_counts = None
    chart_data = None
    if data and data.get("has_data") and data.get("all_operators") and not data["all_operators"].get("error"):
        all_op_top = data["all_operators"].get("top24") or []
        chart_full = _get_chart_data(all_op_top, start_date, end_date, operator=None)
        if chart_full and "totals" in chart_full:
            totals = chart_full["totals"]
            top_numbers_with_counts = sorted(
                [(num, totals.get(num, 0)) for num in all_op_top],
                key=lambda x: -x[1],
            )
            chart_data = {
                "labels": chart_full.get("labels", []),
                "datasets": chart_full.get("datasets", []),
                "filter_label": "All operators",
            }

    payload = {
        "data": data,
        "date_min_csv": date_min_csv or "",
        "date_max_csv": date_max_csv or "",
        "operators": operators,
        "top_numbers_with_counts": top_numbers_with_counts,
        "chart_data": chart_data,
        "start_date": start_date or "",
        "end_date": end_date or "",
        "n": n,
        "bet_types": list(bet_types),
    }
    return JSONResponse(content=payload)


@app.get("/api/chart")
async def api_chart(request: Request):
    """Return chart data as JSON for in-place chart updates (labels + datasets + filter_label)."""
    q = request.query_params
    start_date = q.get("start_date")
    end_date = q.get("end_date")
    n_val = q.get("n")
    chart_operator = q.getlist("chart_operator")
    date_min_csv, date_max_csv = _get_date_range()
    if not start_date and date_min_csv:
        start_date = date_min_csv
    if not end_date and date_max_csv:
        end_date = date_max_csv
    n = 24
    if n_val is not None:
        try:
            n = max(1, min(int(n_val), 1000))
        except ValueError:
            pass
    op_list = [o.strip() for o in chart_operator if o and str(o).strip()]
    payload = _get_chart_api_payload(start_date, end_date, n, op_list if op_list else None)
    if payload is None:
        filter_label = ", ".join(op_list) if op_list else "All operators"
        return JSONResponse(
            content={"labels": [], "datasets": [], "filter_label": filter_label},
            status_code=200,
        )
    return JSONResponse(content=payload)


@app.get("/api/chart/debug")
async def api_chart_debug(request: Request):
    """Echo query params and chart_operator list to verify API receives filter correctly."""
    q = request.query_params
    chart_operator = q.getlist("chart_operator")
    op_list = [o.strip() for o in chart_operator if o and str(o).strip()]
    return JSONResponse(
        content={
            "query_keys": list(q.keys()),
            "chart_operator_raw": chart_operator,
            "chart_operator_parsed": op_list,
            "filter_label": ", ".join(op_list) if op_list else "All operators",
        },
        status_code=200,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/chart", response_class=HTMLResponse)
async def chart_fullscreen(
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    n: int | None = None,
    chart_operator: list[str] | None = None,
):
    """Full-screen chart in a new tab. Same query params as main page; chart drawn via API in JS."""
    date_min_csv, date_max_csv = _get_date_range()
    if start_date is None and date_min_csv:
        start_date = date_min_csv
    if end_date is None and date_max_csv:
        end_date = date_max_csv
    if n is None:
        n = 24
    n = max(1, min(n, 1000))
    operators = _get_operators()
    chart_operators_selected = [o for o in (chart_operator or []) if o and str(o).strip()]
    return templates.TemplateResponse(
        "chart_fullscreen.html",
        {
            "request": request,
            "operators": operators,
            "chart_operators_selected": chart_operators_selected,
            "start_date": start_date or "",
            "end_date": end_date or "",
            "n": n,
        },
    )


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    n: int | None = None,
    chart_operator: list[str] | None = None,
):
    date_min_csv, date_max_csv = _get_date_range()
    if start_date is None and date_min_csv:
        start_date = date_min_csv
    if end_date is None and date_max_csv:
        end_date = date_max_csv
    if n is None:
        n = 24
    n = max(1, min(n, 1000))
    data = _get_all_data(start_date=start_date, end_date=end_date, n=n)
    chart_data = None
    top_numbers_with_counts = None
    operators = _get_operators()
    chart_operators_list = [o for o in (chart_operator or []) if o and str(o).strip()]
    if data and data.get("has_data") and data.get("all_operators") and not data["all_operators"].get("error"):
        all_op_top = data["all_operators"]["top24"]
        chart_top_numbers = _chart_top_numbers_for_operators(
            data, chart_operators_list, start_date or None, end_date or None, n
        )
        operator_filter = chart_operators_list if chart_operators_list else None
        chart_data = _get_chart_data(
            chart_top_numbers,
            start_date=start_date or None,
            end_date=end_date or None,
            operator=operator_filter,
        )
        all_op_chart = chart_data if chart_top_numbers is all_op_top else _get_chart_data(
            all_op_top, start_date or None, end_date or None, operator=None
        )
        if all_op_chart and "totals" in all_op_chart:
            totals = all_op_chart["totals"]
            top_numbers_with_counts = sorted(
                [(num, totals.get(num, 0)) for num in all_op_top],
                key=lambda x: -x[1],
            )
    context = {
        "request": request,
        "data": data,
        "chart_data": chart_data,
        "chart_data_json": json.dumps(
            {k: v for k, v in (chart_data or {}).items() if k != "totals"}
        ) if chart_data else "null",
        "top_numbers_with_counts": top_numbers_with_counts,
        "chart_operators_selected": chart_operators_list,
        "operators": operators,
        "start_date": start_date or "",
        "end_date": end_date or "",
        "n": n,
        "date_min_csv": date_min_csv or "",
        "date_max_csv": date_max_csv or "",
    }
    return templates.TemplateResponse("index.html", context)
