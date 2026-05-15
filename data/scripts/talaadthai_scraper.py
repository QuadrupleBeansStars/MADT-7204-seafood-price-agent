"""Scrape Talaad Thai wholesale prices from talaadthai.com.

Each product page embeds a Next.js ``__NEXT_DATA__`` JSON blob containing
``priceMinThb`` / ``priceMaxThb`` for the latest snapshot. We use the URLs
listed in the ``ตลาดไท`` sheet of the source workbook as the catalog.

Output: ``data/raw/talaadthai_prices.csv`` (append-on-each-run).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_XLSX = REPO_ROOT / "data" / "raw" / "เอเจ้นหาปลา.xlsx"
OUT_CSV = REPO_ROOT / "data" / "raw" / "talaadthai_prices.csv"

NEXT_DATA_RE = re.compile(
    r'__NEXT_DATA__"\s+type="application/json">(.*?)</script>', re.DOTALL
)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Per-URL pricing override: biz wants these SKUs benchmarked at the *ceiling*
# of the daily range (priceMaxThb) rather than the mid-point. Treat the range
# as "what you might pay at the top of the day" — useful when comparing
# retail shops that tend to sit nearer the high end of wholesale.
MAX_PRICE_URLS: set[str] = {
    "https://talaadthai.com/products/squid-9423-3060",
    "https://talaadthai.com/products/saltwater-fish-9433-2433",
}

# Supplementary catalog: items biz wants tracked that aren't yet in the
# source xlsx. Each entry mirrors the columns produced by _load_catalog.
EXTRA_CATALOG_ITEMS: list[dict] = [
    {
        "group_en": "Squid",
        "group_th": "หมึก",
        "item_name_website": "ปลาหมึกกล้วย (ไม่ปอก) ไซส์ใหญ่",
        "link": "https://talaadthai.com/products/squid-9423-3060",
    },
]

logger = logging.getLogger("talaadthai_scraper")


def _fetch(url: str, timeout: int = 20) -> str | None:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        logger.warning("fetch failed url=%s err=%s", url, exc)
        return None


def _parse_price(html: str) -> dict | None:
    m = NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    product = data.get("props", {}).get("pageProps", {}).get("product")
    if not product:
        return None
    pmin = product.get("priceMinThb")
    pmax = product.get("priceMaxThb")
    if pmin is None and pmax is None:
        return None
    snap = (
        product.get("pricingData", {})
        .get("latestPriceDiffProductSnapShot", {})
        .get("data", {})
        .get("current", {})
    )
    return {
        "price_min_thb": pmin,
        "price_max_thb": pmax,
        "unit": product.get("unit"),
        "snapshot_date": snap.get("date"),
    }


def _load_catalog() -> pd.DataFrame:
    df = pd.read_excel(SOURCE_XLSX, sheet_name="ตลาดไท")
    df = df[df["link"].notna() & df["link"].astype(str).str.startswith("https://")]
    df = df.rename(
        columns={
            "Group_Name_TH": "group_th",
            "Group_Name_Eng": "group_en",
            "name from website": "item_name_website",
        }
    )[["group_en", "group_th", "item_name_website", "link"]]
    if EXTRA_CATALOG_ITEMS:
        existing_links = set(df["link"])
        extras = [item for item in EXTRA_CATALOG_ITEMS if item["link"] not in existing_links]
        if extras:
            df = pd.concat([df, pd.DataFrame(extras)], ignore_index=True)
    return df.reset_index(drop=True)


def scrape(limit: int | None = None, sleep_s: float = 0.5) -> pd.DataFrame:
    catalog = _load_catalog()
    if limit:
        catalog = catalog.head(limit)

    today = date.today().isoformat()
    rows: list[dict] = []
    for i, item in catalog.iterrows():
        url = item["link"]
        html = _fetch(url)
        if not html:
            continue
        parsed = _parse_price(html)
        if not parsed:
            logger.info("no price url=%s", url)
            continue
        pmin = parsed["price_min_thb"]
        pmax = parsed["price_max_thb"]
        # Treat 0 as missing (sentinel used by the site for "no data")
        if not pmin and not pmax:
            continue
        if url in MAX_PRICE_URLS:
            # Biz override: benchmark at top of range, falling back to min.
            avg = float(pmax) if pmax else float(pmin)
        elif pmin and pmax:
            avg = (float(pmin) + float(pmax)) / 2
        elif pmin:
            avg = float(pmin)
        elif pmax:
            avg = float(pmax)
        rows.append(
            {
                "scrape_date": today,
                "source": "Talaad Thai",
                "item_name_website": item["item_name_website"],
                "group_en": item["group_en"],
                "group_th": item["group_th"],
                "option": "wholesale",
                "weight_kg": 1.0,
                "selling_price": avg,
                "price_per_kg": avg,
                "price_min_thb": pmin,
                "price_max_thb": pmax,
                "unit": parsed.get("unit"),
                "snapshot_date": parsed.get("snapshot_date"),
                "link": url,
            }
        )
        time.sleep(sleep_s)
        if (i + 1) % 25 == 0:
            logger.info("progress: %d / %d", i + 1, len(catalog))

    return pd.DataFrame(rows)


def write(df: pd.DataFrame) -> None:
    if df.empty:
        logger.warning("no rows scraped; nothing written")
        return
    if OUT_CSV.exists():
        existing = pd.read_csv(OUT_CSV)
        # Drop today's rows from existing to avoid dupes if re-run same day
        today = df["scrape_date"].iloc[0]
        existing = existing[existing["scrape_date"] != today]
        df = pd.concat([existing, df], ignore_index=True)
    df.to_csv(OUT_CSV, index=False)
    logger.info("wrote %d rows to %s", len(df), OUT_CSV)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Scrape Talaad Thai wholesale prices")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of products (debug)")
    parser.add_argument("--sleep", type=float, default=0.5, help="Seconds between requests")
    args = parser.parse_args()

    df = scrape(limit=args.limit, sleep_s=args.sleep)
    logger.info("scraped %d rows", len(df))
    write(df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
