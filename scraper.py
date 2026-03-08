"""
Scraper for check4d.org live 4D results.

Uses requests + BeautifulSoup. Works for server-rendered pages:
- https://www.check4d.org/
- https://www.check4d.org/singapore-4d-results/
- https://www.check4d.org/sabah-sarawak-4d-results/
- https://www.check4d.org/cambodia-4d-results/
"""

from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.check4d.org"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Placeholders that mean "no number" in the HTML
SKIP_VALUES = frozenset({"----", "****", "-", "", "\u00a0", "&nbsp;"})


def _normalize_number(text: str) -> str | None:
    """Return stripped text, or None if it's a placeholder/empty."""
    if not text:
        return None
    t = text.strip().replace("\u00a0", " ").strip()
    if not t or t in SKIP_VALUES:
        return None
    return t


def _parse_draw_date_and_no(cells: list) -> tuple[str | None, str | None]:
    """Extract date and draw number from resultdrawdate cells."""
    date_text, draw_no = None, None
    for td in cells:
        if "resultdrawdate" not in (td.get("class") or []):
            continue
        text = (td.get_text() or "").strip()
        if text.startswith("Date:"):
            date_text = text.replace("Date:", "").strip()
        elif text.startswith("Draw No:"):
            draw_no = text.replace("Draw No:", "").strip()
    return date_text, draw_no


def _collect_numbers_from_cells(cells: list) -> list[str]:
    """Collect valid 4D/similar numbers from resultbottom/resulttop cells."""
    numbers = []
    for td in cells:
        classes = td.get("class") or []
        if "resultbottom" not in classes and "resulttop" not in classes:
            continue
        val = _normalize_number(td.get_text() or "")
        if val is not None:
            numbers.append(val)
    return numbers


def _get_section_numbers_after_header(
    table: Any, header_substring: str
) -> list[str]:
    """In this table, find a row whose first cell contains header_substring, then collect numbers from following rows until next section."""
    numbers = []
    found = False
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        first_text = (tds[0].get_text() or "").strip().lower()
        if header_substring.lower() in first_text and "resultprizelable" in (tds[0].get("class") or []):
            found = True
            continue
        if found:
            if tds and "resultprizelable" in (tds[0].get("class") or []):
                break
            numbers.extend(_collect_numbers_from_cells(tds))
    return numbers


def _get_draw_name_from_first_table(box: Any) -> str:
    """Get draw name from the first table in an outerbox (e.g. 'Magnum 4D 萬能')."""
    first_table = box.find("table", class_="resultTable2")
    if not first_table:
        return ""
    name_classes = (
        "resultm4dlable",
        "resultdamacailable",
        "resulttotolable",
        "resultsg4dlable",
        "resultstc4dlable",
        "resultsteclable",
        "resultsabahlable",
        "resultgdlottolable",
        "resultperdanalable",
        "resulthariharilable",
    )
    tds = first_table.find_all("td")
    for td in tds:
        classes = td.get("class") or []
        if any(c in name_classes for c in classes):
            text = (td.get_text() or "").strip()
            # Prefer cell with actual text (name), not the one that only has an img
            if text and not td.find("img"):
                return text
    for td in tds:
        classes = td.get("class") or []
        if any(c in name_classes for c in classes):
            return (td.get_text() or "").strip()
    if len(tds) >= 2:
        return (tds[1].get_text() or "").strip()
    return ""


def _parse_outerbox(box: Any) -> dict[str, Any]:
    """Parse one outerbox div into a structured draw result."""
    draw_name = _get_draw_name_from_first_table(box)
    tables = box.find_all("table", class_="resultTable2")
    result: dict[str, Any] = {
        "draw_name": draw_name,
        "date": None,
        "draw_no": None,
        "first_prize": None,
        "second_prize": None,
        "third_prize": None,
        "special": [],
        "consolation": [],
        "jackpot_amounts": {},
    }

    for table in tables:
        rows = table.find_all("tr")
        for tr in rows:
            tds = tr.find_all("td")
            if not tds:
                continue
            classes_0 = tds[0].get("class") or []

            # Date and draw number
            if "resultdrawdate" in classes_0:
                result["date"], result["draw_no"] = _parse_draw_date_and_no(tds)
                continue

            # Top 3 prizes: label in first cell, number in second (resulttop)
            if "resultprizelable" in classes_0 and len(tds) >= 2:
                label = (tds[0].get_text() or "").strip().lower()
                val = _normalize_number(tds[1].get_text() or "")
                if not val:
                    continue
                if "1st" in label or "首" in label:
                    result["first_prize"] = val
                elif "2nd" in label or "二" in label:
                    result["second_prize"] = val
                elif "3rd" in label or "三" in label:
                    result["third_prize"] = val

            # Special / Consolation sections (header row)
            first_text = (tds[0].get_text() or "").strip()
            if "special" in first_text.lower() or "特別" in first_text:
                result["special"] = _get_section_numbers_after_header(table, "Special")
                break
            if "consolation" in first_text.lower() or "安慰" in first_text:
                result["consolation"] = _get_section_numbers_after_header(table, "Consolation")
                break

        # Jackpot amounts (result5dprizelable with "RM" or "$")
        for td in table.find_all("td", class_="result5dprizelable"):
            text = (td.get_text() or "").strip()
            if "RM" in text or "$" in text:
                # Simple extraction: "4D Jackpot 1 Prize" -> key, "RM 10,206,413.40" -> value
                b = td.find("b")
                if b:
                    amount = (b.get_text() or "").strip()
                    if amount:
                        prev = td.find_previous("td", class_="resultprizelable")
                        if prev:
                            label = (prev.get_text() or "").strip()
                            if label and label not in result["jackpot_amounts"]:
                                result["jackpot_amounts"][label] = amount

    # If we didn't get special/consolation from section parse, collect from resultbottom
    if not result["special"] or not result["consolation"]:
        for table in tables:
            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                header = (tds[0].get_text() if tds else "") or ""
                if "special" in header.lower() or "特別" in header:
                    for r in tr.find_next_siblings("tr"):
                        cells = r.find_all("td")
                        if cells and "resultprizelable" in (cells[0].get("class") or []):
                            break
                        result["special"].extend(_collect_numbers_from_cells(cells))
                    break
                if "consolation" in header.lower() or "安慰" in header:
                    for r in tr.find_next_siblings("tr"):
                        cells = r.find_all("td")
                        if cells and "resultprizelable" in (cells[0].get("class") or []):
                            break
                        result["consolation"].extend(_collect_numbers_from_cells(cells))
                    break

    # Dedupe and filter empty
    result["special"] = [n for n in result["special"] if _normalize_number(n)]
    result["consolation"] = [n for n in result["consolation"] if _normalize_number(n)]
    return result


def fetch_page(url: str, session: requests.Session | None = None) -> str:
    """Fetch HTML from URL. Uses session if provided."""
    sess = session or requests.Session()
    resp = sess.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def scrape_url(url: str) -> list[dict[str, Any]]:
    """
    Scrape a check4d.org results page and return a list of draw results.

    Each item has: draw_name, date, draw_no, first_prize, second_prize, third_prize,
    special, consolation, jackpot_amounts.
    """
    html = fetch_page(url)
    soup = BeautifulSoup(html, "html.parser")
    boxes = soup.select("div.outerbox")
    return [_parse_outerbox(box) for box in boxes]


def scrape_live() -> list[dict[str, Any]]:
    """Scrape the main live results page (all regions)."""
    return scrape_url(f"{BASE_URL}/")


def scrape_singapore() -> list[dict[str, Any]]:
    """Scrape Singapore 4D/Toto results only."""
    return scrape_url(f"{BASE_URL}/singapore-4d-results/")


def scrape_sabah_sarawak() -> list[dict[str, Any]]:
    """Scrape Sabah/Sarawak results only."""
    return scrape_url(f"{BASE_URL}/sabah-sarawak-4d-results/")


def scrape_cambodia() -> list[dict[str, Any]]:
    """Scrape Cambodia results only."""
    return scrape_url(f"{BASE_URL}/cambodia-4d-results/")


def fetch_past_date(date_str: str, session: requests.Session | None = None) -> str:
    """
    Fetch past results HTML for a given date via POST.
    date_str: YYYY-MM-DD (e.g. '2026-03-07').
    """
    sess = session or requests.Session()
    resp = sess.post(
        f"{BASE_URL}/past-results",
        data={"datepicker": date_str},
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def parse_results_html(html: str, parser: str = "lxml") -> list[dict[str, Any]]:
    """Parse HTML (from live or past-results page) into list of draw dicts.
    Uses 'lxml' for speed when available, falls back to 'html.parser'.
    """
    try:
        soup = BeautifulSoup(html, parser)
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    boxes = soup.select("div.outerbox")
    return [_parse_outerbox(box) for box in boxes]


def scrape_past_date(date_str: str) -> list[dict[str, Any]]:
    """Scrape past results for one date (YYYY-MM-DD). Returns all draws for that date."""
    html = fetch_past_date(date_str)
    return parse_results_html(html)
