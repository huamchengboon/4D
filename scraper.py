"""
Scraper for check4d.org live 4D results.

Uses requests + BeautifulSoup. Works for server-rendered pages:
- https://www.check4d.org/
- https://www.check4d.org/singapore-4d-results/
- https://www.check4d.org/sabah-sarawak-4d-results/
- https://www.check4d.org/cambodia-4d-results/
"""

from typing import Any

import re

import os
import time

import requests
from bs4 import BeautifulSoup

CHECK4D_BASE_URL_HTTPS = "https://www.check4d.org"
CHECK4D_BASE_URL_HTTP = "http://www.check4d.org"

# Default base URL used for live scraping and for past-results scraping (HTTPS first).
BASE_URL = CHECK4D_BASE_URL_HTTPS
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Network tuning for environments that may get throttled/blocked.
CHECK4D_TIMEOUT_SECONDS = float(os.environ.get("CHECK4D_TIMEOUT_SECONDS", "20"))
CHECK4D_MAX_RETRIES = int(os.environ.get("CHECK4D_MAX_RETRIES", "3"))
CHECK4D_RETRY_BACKOFF_SECONDS = float(os.environ.get("CHECK4D_RETRY_BACKOFF_SECONDS", "1.5"))

# Placeholders that mean "no number" in the HTML
SKIP_VALUES = frozenset({"----", "****", "-", "", "\u00a0", "&nbsp;"})

#
# Multi-source integration (past results)
#

CANONICAL_OPERATOR_NAMES: dict[str, str] = {
    "Magnum 4D": "Magnum 4D",
    "Da Ma Cai 1+3D": "Da Ma Cai 1+3D",
    "Sports Toto 4D": "Sports Toto 4D",
}

# Operator set we require a scraper to produce for a given date.
#
# This is intentionally strict so we can failover cleanly and avoid
# partially-filled rows marking a date as "done".
REQUIRED_OPERATORS: frozenset[str] = frozenset(
    ["Magnum 4D", "Da Ma Cai 1+3D", "Sports Toto 4D"]
)


def _normalize_operator_name_for_draw(draw_name: str) -> str:
    """Mirror `scrape_history.normalize_operator_name` without importing it."""
    if "Magnum 4D" in (draw_name or ""):
        return "Magnum 4D"
    if "Da Ma Cai 1+3D" in (draw_name or "") or (
        "Da Ma Cai" in (draw_name or "") and "1+3D" in (draw_name or "")
    ):
        return "Da Ma Cai 1+3D"
    if (
        ("Sports Toto 4D" in (draw_name or "") or "SportsToto 4D" in (draw_name or ""))
        and "5D" not in (draw_name or "")
        and "6D" not in (draw_name or "")
        and "Lotto" not in (draw_name or "")
    ):
        return "Sports Toto 4D"
    return ""


def _draw_is_complete(draw: dict[str, Any]) -> bool:
    return bool(
        draw.get("draw_no")
        and draw.get("first_prize")
        and draw.get("second_prize")
        and draw.get("third_prize")
        and (draw.get("special") or [])
        and (draw.get("consolation") or [])
    )


def _draws_have_required_complete_operators(draws: list[dict[str, Any]]) -> bool:
    seen: set[str] = set()
    for d in draws:
        op = _normalize_operator_name_for_draw(d.get("draw_name") or "")
        if not op or op not in REQUIRED_OPERATORS:
            continue
        if _draw_is_complete(d):
            seen.add(op)
    return REQUIRED_OPERATORS.issubset(seen)


def _get_scrape_sources_from_env() -> list[str]:
    # Default: original check4d, then 4dmy (covers Magnum + Da Ma Cai + Sports Toto),
    # then 4dkingdom as a third fallback.
    raw = os.environ.get("SCRAPE_SOURCES", "4dmy,4dkingdom,check4d").strip()
    if not raw:
        return ["4dmy", "4dkingdom", "check4d"]
    return [s.strip() for s in raw.split(",") if s.strip()]


def scrape_past_date(date_str: str, sources: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Fetch and parse past results for `date_str` (YYYY-MM-DD).

    Tries sources in order until at least one relevant draw is parsed.
    Returns draw dicts compatible with `scrape_history.draw_to_rows()`.
    """
    candidate_sources = sources or _get_scrape_sources_from_env()
    last_err: Exception | None = None
    for src in candidate_sources:
        try:
            draws = _scrape_past_date_from_source(src, date_str)
            if draws and _draws_have_required_complete_operators(draws):
                return draws
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    return []


def _scrape_past_date_from_source(source: str, date_str: str) -> list[dict[str, Any]]:
    if source == "check4d":
        html = fetch_past_date(date_str)
        return parse_results_html(html)
    if source == "4dmy":
        return _scrape_past_date_4dmy(date_str)
    if source == "4dkingdom":
        return _scrape_past_date_4dkingdom(date_str)
    raise ValueError(f"Unknown scrape source: {source}")


def _parse_yyyy_mm_dd(date_str: str) -> tuple[str, str, str] | None:
    parts = date_str.split("-")
    if len(parts) != 3:
        return None
    y, m, d = parts
    if len(y) != 4 or len(m) != 2 or len(d) != 2:
        return None
    return y, m, d


def _norm4(num: str) -> str | None:
    s = str(num).strip()
    if not s or not s.isdigit() or len(s) > 4:
        return None
    return s.zfill(4)


def _fetch_text(url: str) -> str:
    sess = requests.Session()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        # Keep connections warm when possible.
        "Connection": "keep-alive",
    }

    fallback_to_http = os.environ.get("CHECK4D_FALLBACK_TO_HTTP", "true").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    urls_to_try = [url]
    if fallback_to_http and url.startswith("https://"):
        urls_to_try.append(url.replace("https://", "http://", 1))

    last_exc: Exception | None = None
    for try_url in urls_to_try:
        for attempt in range(CHECK4D_MAX_RETRIES):
            try:
                resp = sess.get(try_url, headers=headers, timeout=CHECK4D_TIMEOUT_SECONDS)
                # Treat rate limits + transient 5xx as retryable.
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_exc = RuntimeError(
                        f"HTTP {resp.status_code} while fetching {try_url}"
                    )
                    if attempt + 1 < CHECK4D_MAX_RETRIES:
                        time.sleep(CHECK4D_RETRY_BACKOFF_SECONDS * (attempt + 1))
                        continue
                    resp.raise_for_status()
                resp.raise_for_status()
                resp.encoding = resp.encoding or "utf-8"
                return resp.text
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                if attempt + 1 < CHECK4D_MAX_RETRIES:
                    time.sleep(CHECK4D_RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise
    raise last_exc or RuntimeError(f"Failed to fetch {url}")


def _extract_4digit_numbers(text: str) -> list[str]:
    # Match exact 4-digit numbers, but avoid capturing parts of longer digit sequences.
    return [m.group(1) for m in re.finditer(r"(?<!\d)(\d{4})(?!\d)", text)]


def _extract_draw_no(block_text: str) -> str:
    m = re.search(r"Draw No\.?\s*:?\s*([0-9]+/[0-9]+)", block_text)
    return m.group(1).strip() if m else ""


def _extract_prize(block_text: str, prize_label: str) -> str | None:
    m = re.search(rf"{re.escape(prize_label)}[^0-9]*([0-9]{{1,4}})", block_text)
    return _norm4(m.group(1)) if m else None


def _extract_special_and_consolation(block_text: str) -> tuple[list[str], list[str]]:
    # Extract only inside Special..Consolation to avoid picking up draw_no digits.
    special_nums: list[str] = []
    consolation_nums: list[str] = []
    m_special = re.search(
        r"Special\b(.*?)(Consolation\b)",
        block_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if m_special:
        special_nums = _extract_4digit_numbers(m_special.group(1))
    m_consol = re.search(
        r"Consolation\b(.*)$", block_text, flags=re.DOTALL | re.IGNORECASE
    )
    if m_consol:
        consolation_nums = _extract_4digit_numbers(m_consol.group(1))
    return special_nums, consolation_nums


def _scrape_past_date_4dmy(date_str: str) -> list[dict[str, Any]]:
    # 4DMy uses DD-MM-YYYY in URL.
    parts = _parse_yyyy_mm_dd(date_str)
    if not parts:
        return []
    y, m, d = parts
    url = f"https://www.4dmy.com/past-results-history/{d}-{m}-{y}"
    html = _fetch_text(url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    def block(start_marker: str, end_marker: str) -> str:
        start = text.find(start_marker)
        if start == -1:
            return ""
        end = text.find(end_marker, start + len(start_marker))
        if end == -1:
            end = len(text)
        return text[start:end]

    damacai_block = block("Da Ma Cai 1+3D", "Magnum 4D")
    magnum_block = block("Magnum 4D", "SportsToto 4D")
    sportstoto_block = block("SportsToto 4D", "Sabah 88 4D")

    draws: list[dict[str, Any]] = []
    for draw_name, b in [
        ("Da Ma Cai 1+3D", damacai_block),
        ("Magnum 4D", magnum_block),
        ("Sports Toto 4D", sportstoto_block),
    ]:
        if not b.strip():
            continue
        draw_no = _extract_draw_no(b)
        first = _extract_prize(b, "1st Prize")
        second = _extract_prize(b, "2nd Prize")
        third = _extract_prize(b, "3rd Prize")
        special, consolation = _extract_special_and_consolation(b)
        if not (draw_no and first and second and third and special and consolation):
            continue
        draws.append(
            {
                "draw_name": draw_name,
                "draw_no": draw_no,
                "first_prize": first,
                "second_prize": second,
                "third_prize": third,
                "special": special,
                "consolation": consolation,
                "jackpot_amounts": {},
            }
        )
    return draws


def _scrape_past_date_4dkingdom(date_str: str) -> list[dict[str, Any]]:
    url = f"https://www.4dkingdom.com/past-results/{date_str}"
    html = _fetch_text(url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    def block(start_marker: str, end_marker: str) -> str:
        start = text.find(start_marker)
        if start == -1:
            return ""
        end = text.find(end_marker, start + len(start_marker))
        if end == -1:
            end = len(text)
        return text[start:end]

    # The page includes many sections; we partition using the operators we care about.
    magnum_block = block("Magnum", "Sports Toto")
    sportstoto_block = block("Sports Toto", "Damacai")
    damacai_block = block("Damacai", "Sports Toto")

    draws: list[dict[str, Any]] = []
    for draw_name, b in [
        ("Magnum 4D", magnum_block),
        ("Sports Toto 4D", sportstoto_block),
        ("Da Ma Cai 1+3D", damacai_block),
    ]:
        if not b.strip():
            continue
        draw_no = _extract_draw_no(b)
        first = _extract_prize(b, "1st Prize")
        second = _extract_prize(b, "2nd Prize")
        third = _extract_prize(b, "3rd Prize")
        special, consolation = _extract_special_and_consolation(b)
        if not (draw_no and first and second and third and special and consolation):
            continue
        draws.append(
            {
                "draw_name": draw_name,
                "draw_no": draw_no,
                "first_prize": first,
                "second_prize": second,
                "third_prize": third,
                "special": special,
                "consolation": consolation,
                "jackpot_amounts": {},
            }
        )
    return draws


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
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    last_exc: Exception | None = None
    for attempt in range(CHECK4D_MAX_RETRIES):
        try:
            resp = sess.get(
                url,
                headers=headers,
                timeout=CHECK4D_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            # Backoff to avoid hammering when throttled.
            time.sleep(CHECK4D_RETRY_BACKOFF_SECONDS * (attempt + 1))
        except requests.exceptions.HTTPError as exc:
            # Retry only for rate-limit / transient server issues.
            last_exc = exc
            status = getattr(exc.response, "status_code", None)
            if status in (429, 500, 502, 503, 504) and attempt + 1 < CHECK4D_MAX_RETRIES:
                time.sleep(CHECK4D_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
    raise last_exc or RuntimeError(f"Failed to fetch {url}")


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
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        # Past results endpoint is date-specific; these help look more like a browser.
        "Content-Type": "application/x-www-form-urlencoded",
    }
    last_exc: Exception | None = None
    fallback_to_http = os.environ.get("CHECK4D_FALLBACK_TO_HTTP", "true").lower() in ("1", "true", "yes", "on")

    # Try HTTPS first, then optionally fall back to HTTP if outbound 443 is blocked.
    base_urls = [CHECK4D_BASE_URL_HTTPS]
    if fallback_to_http:
        base_urls.append(CHECK4D_BASE_URL_HTTP)

    for base_url in base_urls:
        last_exc = None
        for attempt in range(CHECK4D_MAX_RETRIES):
            try:
                resp = sess.post(
                    f"{base_url}/past-results",
                    data={"datepicker": date_str},
                    headers=headers,
                    timeout=CHECK4D_TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
                resp.encoding = resp.encoding or "utf-8"
                return resp.text
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                time.sleep(CHECK4D_RETRY_BACKOFF_SECONDS * (attempt + 1))
            except requests.exceptions.HTTPError as exc:
                # For HTTP errors, retry only for transient statuses; otherwise fail fast.
                last_exc = exc
                status = getattr(exc.response, "status_code", None)
                if status in (429, 500, 502, 503, 504) and attempt + 1 < CHECK4D_MAX_RETRIES:
                    time.sleep(CHECK4D_RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise

    raise last_exc or RuntimeError(f"Failed to fetch past results for {date_str}")


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


def _scrape_past_date_check4d(date_str: str) -> list[dict[str, Any]]:
    """Scrape past results for one date using check4d.org only."""
    html = fetch_past_date(date_str)
    return parse_results_html(html)
