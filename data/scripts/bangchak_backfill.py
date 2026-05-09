"""One-shot backfill of weekly Bangchak ไฮดีเซลฯ (Hi Diesel S) prices.

The bangchak.co.th historical page is gated by a Radware captcha, so this
loader doesn't fetch — it ingests:
  1. A locally saved HTML page (e.g. ``data/raw/bangchak/year_2569.html``),
     parsing the table for the ``Hi Diesel S`` column.
  2. Hand-transcribed weekly rows for years where we only have screenshots.

Output: appends to ``data/raw/oil_prices.csv`` with ``source='bangchak'``
and ``product='Diesel'`` so the rows merge with the daily thaioil scrape on
load. Idempotent — existing (date, product, source) tuples are skipped.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "raw" / "oil_prices.csv"
HTML_DIR = REPO_ROOT / "data" / "raw" / "bangchak"

SOURCE = "bangchak"
PRODUCT = "Diesel"  # ไฮดีเซลฯ (Hi Diesel S) -> store as 'Diesel' for series merge

# Hand-transcribed weekly Hi Diesel S prices from year 2568 (2025) screenshot.
# Two rows obscured by the cookie banner are intentionally omitted.
HISTORICAL_2568: list[tuple[str, float]] = [
    ("24/12/2568", 30.44),
    ("21/10/2568", 30.94),
    ("04/10/2568", 31.44),
    ("24/09/2568", 31.94),
    ("22/08/2568", 31.94),
    ("09/08/2568", 31.94),
    ("01/08/2568", 31.94),
    ("24/07/2568", 31.94),
    ("02/07/2568", 31.94),
    ("26/06/2568", 31.94),
    ("24/06/2568", 31.94),
    ("20/06/2568", 31.94),
    ("13/06/2568", 31.94),
    ("22/05/2568", 31.94),
    ("12/04/2568", 31.94),
    ("09/04/2568", 31.94),
    ("04/04/2568", 31.94),
    ("28/03/2568", 32.44),
    ("11/03/2568", 32.94),
    ("06/03/2568", 32.94),
    ("28/02/2568", 32.94),
    ("20/02/2568", 32.94),
    ("06/02/2568", 32.94),
    ("23/01/2568", 32.94),
    ("15/01/2568", 32.94),
    ("11/01/2568", 32.94),
    ("03/01/2568", 32.94),
]


def be_to_iso(date_be: str) -> str:
    """Convert 'DD/MM/YYYY' (Buddhist Era) to 'YYYY-MM-DD' (Gregorian)."""
    d, m, y = date_be.split("/")
    return f"{int(y) - 543:04d}-{int(m):02d}-{int(d):02d}"


def parse_html_file(path: Path) -> list[tuple[str, float]]:
    """Parse a saved Bangchak historical year page; return [(date_be, price)]."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    table = soup.find("table")
    if not table:
        return []
    rows: list[tuple[str, float]] = []
    for tr in table.find_all("tr"):
        th = tr.find("th", scope="row")
        if not th:
            continue
        date_be = th.get_text(strip=True)
        td = tr.find("td", title="Hi Diesel S")
        if not td:
            continue
        try:
            rows.append((date_be, float(td.get_text(strip=True))))
        except ValueError:
            continue
    return rows


def existing_keys() -> set[tuple[str, str, str]]:
    if not OUT_PATH.exists():
        return set()
    out: set[tuple[str, str, str]] = set()
    with OUT_PATH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.add((r["date"], r["product"], r["source"]))
    return out


def append_rows(rows: list[tuple[str, float]]) -> int:
    keys = existing_keys()
    new = [(be_to_iso(d), p) for d, p in rows]
    new_file = not OUT_PATH.exists()
    written = 0
    with OUT_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "product", "thb_per_litre", "source"])
        if new_file:
            w.writeheader()
        for iso_date, price in new:
            if (iso_date, PRODUCT, SOURCE) in keys:
                continue
            w.writerow({
                "date": iso_date,
                "product": PRODUCT,
                "thb_per_litre": price,
                "source": SOURCE,
            })
            written += 1
    return written


def main() -> int:
    rows: list[tuple[str, float]] = list(HISTORICAL_2568)

    if HTML_DIR.exists():
        for html_file in sorted(HTML_DIR.glob("*.html")):
            parsed = parse_html_file(html_file)
            print(f"[bangchak_backfill] {html_file.name}: {len(parsed)} rows")
            rows.extend(parsed)

    if not rows:
        print("[bangchak_backfill] no rows to ingest", file=sys.stderr)
        return 1

    n = append_rows(rows)
    print(f"[bangchak_backfill] appended {n} new rows to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
