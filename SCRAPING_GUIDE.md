# Scraping check4d.org – Guide

How to scrape [check4d.org](https://www.check4d.org) for 4D results (Magnum, Da Ma Cai, Sports Toto, Singapore, Sabah/Sarawak, Cambodia).

---

## 1. Site structure

### Pages and URLs

| Page | URL | Content |
|------|-----|--------|
| **Live results (all)** | `https://www.check4d.org/` | West MY, East MY, SG, Cambodia – full HTML |
| **Singapore only** | `https://www.check4d.org/singapore-4d-results/` | Singapore 4D + Toto |
| **Sabah/Sarawak** | `https://www.check4d.org/sabah-sarawak-4d-results/` | Sandakan, CashSweep, Sabah 88 |
| **Cambodia** | `https://www.check4d.org/cambodia-4d-results/` | Grand Dragon, Perdana, Lucky HariHari |
| **Past results** | `https://www.check4d.org/past-results` | Date picker; content may load via JS |

### Rendering

- **Main result pages** (home, Singapore, Sabah/Sarawak, Cambodia): **server-rendered HTML**. All result tables are in the initial response. You can scrape with **requests + BeautifulSoup** only; no browser/Playwright needed.
- **Past results**: Uses a date picker and may load results via JavaScript. For past dates you may need **Playwright** (or similar) to select a date and wait for content, unless you discover an API or direct URL pattern.

---

## 2. HTML structure (live results)

- Results are in **`<div class="outerbox">`** blocks.
- Each block contains several **`<table class="resultTable2">`** tables.
- Pattern inside each block:
  1. **Header**: Logo + draw name (e.g. “Magnum 4D 萬能”).
  2. **Date / draw no**: Rows with `class="resultdrawdate"` (e.g. `Date: 07-03-2026 (Sat)`, `Draw No: 337/26`).
  3. **Top 3**: Rows with `class="resulttop"` (1st, 2nd, 3rd prize).
  4. **Special (特別獎)**: Rows with `class="resultbottom"` under a “Special” header.
  5. **Consolation (安慰獎)**: Same, under “Consolation”.
  6. **Jackpot / extra**: Rows with `class="result5dprizelable"` for amounts.

### Useful CSS classes

| Class | Meaning |
|-------|--------|
| `resultdrawdate` | Date and draw number text |
| `resulttop` | 1st / 2nd / 3rd prize numbers |
| `resultbottom` | Special and consolation numbers |
| `resultprizelable` | Section title (e.g. “Special”, “Consolation”) |
| `result5dprizelable` | Jackpot amounts, 5D/6D labels |
| `resultm4dlable`, `resultdamacailable`, `resulttotolable`, etc. | Draw name (Magnum, Da Ma Cai, Toto, etc.) |

### Element IDs (examples)

Many cells have stable IDs, e.g.:

- Magnum: `mdd`, `mdn`, `mp1`–`mp3`, `ms1`–`ms13`, `mc1`–`mc10`, `mjp1`, `mjp2`.
- Da Ma Cai: `ddd`, `ddn`, `dp1`–`dp3`, `ds1`–`ds10`, `dc1`–`dc10`, `djp1`–`djp3`.
- Sports Toto: `tdd`, `tdn`, `tp1`–`tp3`, `ts1`–`ts13`, `tc1`–`tc10`, `tjp1`, `tjp2`.
- Singapore: `sdd`, `sdn`, `sp1`–`sp3`, `ss1`–`ss10`, `sc1`–`sc10`.

You can use these IDs for targeted extraction if you prefer.

---

## 3. Recommended approach

### Option A: requests + BeautifulSoup (live results)

1. **GET** the page (e.g. `https://www.check4d.org/`).
2. Parse with **BeautifulSoup**.
3. Find all **`.outerbox`** divs.
4. For each box:
   - Get draw name from the first table (logo + text).
   - Get date/draw from `resultdrawdate` cells.
   - Get 1st/2nd/3rd from `resulttop` cells.
   - Get special/consolation from `resultbottom` cells (skip header rows by checking for `resultprizelable`).
   - Get jackpot/estimated amounts from `result5dprizelable` where relevant.
5. Normalize numbers (strip `----`, `****`, `&nbsp;`, etc.) and store as you need (e.g. JSON/dict per draw).

**Pros**: Simple, fast, no browser.  
**Cons**: Only what’s in the initial HTML (works for all live result pages above).

### Option B: Playwright (if you need past results)

1. Open `https://www.check4d.org/past-results`.
2. Use the date picker (month/year + calendar) to choose a date.
3. Wait for the result content to load (e.g. wait for `.outerbox` or specific result text).
4. Parse the loaded HTML with BeautifulSoup (or Playwright’s own selectors) using the same structure as above.

**Pros**: Can scrape past results that depend on JS.  
**Cons**: Heavier setup and slower.

---

## 4. Practical tips

- **User-Agent**: Send a normal browser User-Agent to reduce risk of being blocked, e.g.  
  `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 …`
- **Rate limiting**: Don’t hammer the site; add a small delay between requests (e.g. 1–2 seconds) if you scrape multiple pages or dates.
- **Placeholders**: Filter or normalize values like `----`, `****`, `\----`, `&nbsp;` when storing numbers.
- **Encodings**: Page is UTF-8; use `response.encoding = 'utf-8'` (or rely on requests’ detection) so Chinese text (e.g. 首獎, 特別獎) parses correctly.
- **Regions**: Use the region-specific URLs above to get smaller HTML and only the draws you need.

---

## 5. Example: minimal flow

```python
import requests
from bs4 import BeautifulSoup

url = "https://www.check4d.org/"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 ..."})
resp.raise_for_status()
soup = BeautifulSoup(resp.text, "html.parser")

for box in soup.select("div.outerbox"):
    tables = box.find_all("table", class_="resultTable2")
    # First table: name; next: date/draw; then top 3; then special; then consolation; etc.
    # Parse accordingly and build a dict per draw.
```

The `check4d` package in this repo implements this flow and returns structured data for each draw.

---

## 6. Speed: parallel fetch and optional Rust

- **Python**: `scrape_history.py` uses multiple workers by default (`--workers 20`) to fetch many dates in parallel (thread pool). No delay between requests when using workers.
- **Parsing**: Uses `lxml` for faster HTML parsing when available.
- **Rust (optional)**: For maximum speed, build the PyO3 extension so Python uses Rust for parallel HTTP:
  1. Install [Rust](https://rustup.rs) and [maturin](https://pypi.org/project/maturin/): `pip install maturin`
  2. From project root: `maturin develop`
  3. Run `scrape_history.py` as usual; it will use the Rust fetcher when available.

---

## 7. Legal / ethics

- Use scraped data for personal or educational use only.
- Respect the site’s terms of use and robots.txt.
- Avoid overloading the server; keep request rate low.
