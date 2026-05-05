"""Daily scraper for Thai oil retail prices from thaioilgroup.com.

Parses the HTML, pairs each <img alt="..."> with the immediately following
<p class="oil-price">N</p>, and appends one row per product to
data/raw/oil_prices.csv. Idempotent — skips if today's source rows already
exist.
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.thaioilgroup.com/en/oil-prices-information/"
OUT_PATH = Path(__file__).resolve().parent.parent / "raw" / "oil_prices.csv"
SOURCE = "thaioil"


def parse_oil_prices(html: str) -> list[dict]:
    """Return [{"product": str, "thb_per_litre": float}, ...] from page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    prices = soup.select("p.oil-price")
    if not prices:
        raise ValueError("no oil prices found in HTML — page structure may have changed")

    rows: list[dict] = []
    for p_tag in prices:
        img = p_tag.find_previous("img", alt=True)
        if img is None or not img.get("alt"):
            continue
        try:
            value = float(p_tag.get_text(strip=True))
        except ValueError:
            continue
        rows.append({"product": img["alt"].strip(), "thb_per_litre": value})

    if not rows:
        raise ValueError("no oil prices found — img/p pairing failed")
    return rows


def fetch_html(url: str = URL, timeout: int = 30) -> str:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "MADT-7204-bot/1.0"})
    resp.raise_for_status()
    return resp.text


def append_rows(rows: list[dict], today: date, out_path: Path = OUT_PATH) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists()
    written = 0
    with out_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "product", "thb_per_litre", "source"])
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow({"date": today.isoformat(), "source": SOURCE, **r})
            written += 1
    return written


def already_scraped_today(today: date, out_path: Path = OUT_PATH) -> bool:
    if not out_path.exists():
        return False
    with out_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return any(r["date"] == today.isoformat() and r["source"] == SOURCE for r in reader)


def main() -> int:
    today = date.today()
    if already_scraped_today(today):
        print(f"[oil_scraper] already scraped {today}, skipping")
        return 0
    try:
        html = fetch_html()
        rows = parse_oil_prices(html)
    except Exception as e:
        print(f"[oil_scraper] FAILED: {e}", file=sys.stderr)
        return 1
    n = append_rows(rows, today)
    print(f"[oil_scraper] wrote {n} rows for {today}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
