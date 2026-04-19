"""
Daily seafood price scraper for 7 Bangkok online shops.

Visits known product URLs from the registry CSV, extracts current prices,
and appends timestamped rows to data/raw/seafood_prices.csv.

Usage:
    conda activate MADT
    python data/scripts/scraper.py              # scrape all sites
    python data/scripts/scraper.py --test       # scrape 1 URL per site (dry run)

Sites:
    1. taikongseafood.com       — WooCommerce, HTML with <select> variants
    2. sawasdeeseafood.com      — WooCommerce, single-SKU products
    3. henghengseafood.com      — WooCommerce, <select> variants (price hidden)
    4. ppnseafoodwishing.com    — WooCommerce, <select> variants
    5. supremeseafoods.net      — Page365 JSON API (no HTML)
    6. siriratseafood.com       — WooCommerce, <select> variants
    7. sirinfarm.com            — WooCommerce, single-SKU products
"""

import argparse
import csv
import json
import logging
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "raw"
REGISTRY_CSV = DATA_DIR / "เอเจ้นหาปลา - working sheet (tarn).csv"
OUTPUT_CSV = DATA_DIR / "seafood_prices.csv"

FIELDNAMES = [
    "scrape_date",
    "source",
    "item_name_website",
    "group_en",
    "group_th",
    "option",
    "weight_kg",
    "selling_price",
    "price_per_kg",
    "link",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_DELAY = 1.5  # seconds between requests to same domain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_price(text: str) -> float | None:
    """Extract a numeric price from text like '฿850.00' or '690 บาท'."""
    if not text:
        return None
    cleaned = text.replace(",", "").replace("฿", "").replace("บาท", "").strip()
    match = re.search(r"[\d]+(?:\.[\d]+)?", cleaned)
    if match:
        val = float(match.group())
        return val if val > 0 else None
    return None


def _fetch(url: str) -> requests.Response | None:
    """Fetch a URL with error handling."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        log.warning("Failed to fetch %s: %s", url, e)
        return None


def _soup(url: str) -> BeautifulSoup | None:
    """Fetch and parse an HTML page."""
    resp = _fetch(url)
    if resp is None:
        return None
    return BeautifulSoup(resp.text, "html.parser")


# ---------------------------------------------------------------------------
# Per-site parsers
# ---------------------------------------------------------------------------

def parse_woocommerce(soup: BeautifulSoup, url: str) -> list[dict]:
    """Generic WooCommerce parser — works for most Thai seafood shops.

    Extraction priority:
    1. data-product_variations JSON on <form class="variations_form">
       — gives exact per-variant prices (taikong, sawasdee, ppn)
    2. Single <p class="price"> text — for single-SKU products (sirinfarm)
    3. Price range text — parsed as fallback (sirirat)
    """
    results = []

    # Product title
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else "Unknown"

    # --- Strategy 1: WooCommerce variations JSON ---
    form = soup.find("form", class_="variations_form")
    if form and form.get("data-product_variations"):
        try:
            variations = json.loads(form["data-product_variations"])
            for v in variations:
                attrs = v.get("attributes", {})
                # Attribute values may be URL-encoded Thai text
                from urllib.parse import unquote
                opt_name = unquote(list(attrs.values())[0]) if attrs else "-"
                price = v.get("display_price")
                results.append({
                    "item_name_website": title,
                    "option": opt_name,
                    "selling_price": float(price) if price else None,
                })
            if results:
                return results
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            log.warning("Failed to parse variations JSON for %s: %s", url, e)

    # --- Strategy 2: Single price from <p class="price"> ---
    price_el = soup.find("p", class_="price")
    price_text = price_el.get_text(strip=True) if price_el else ""

    if price_text:
        # Check if it's a single price (not a range)
        prices_found = re.findall(r"[\d,]+(?:\.[\d]+)?", price_text)
        if len(prices_found) == 1:
            price = _parse_price(prices_found[0])
            results.append({
                "item_name_website": title,
                "option": "-",
                "selling_price": price,
            })
            return results

    # --- Strategy 3: No extractable price ---
    # Return the product with no price — the registry CSV has the baseline
    results.append({
        "item_name_website": title,
        "option": "-",
        "selling_price": None,
    })
    return results


def parse_supreme(url: str) -> list[dict]:
    """Supreme Seafoods uses Page365 — returns JSON directly."""
    resp = _fetch(url)
    if resp is None:
        return []

    try:
        data = resp.json()
    except ValueError:
        log.warning("Supreme Seafoods: non-JSON response from %s", url)
        return []

    name = data.get("name", "Unknown")
    price = data.get("price")
    variants = data.get("variants", [])

    results = []
    if variants and len(variants) > 1:
        for v in variants:
            v_name = v.get("name") or "-"
            v_price = v.get("price") or price
            results.append({
                "item_name_website": name,
                "option": v_name,
                "selling_price": float(v_price) if v_price else None,
            })
    else:
        results.append({
            "item_name_website": name,
            "option": "-",
            "selling_price": float(price) if price else None,
        })

    return results


# ---------------------------------------------------------------------------
# Domain → parser dispatch
# ---------------------------------------------------------------------------

WOOCOMMERCE_DOMAINS = {
    "taikongseafood.com",
    "www.sawasdeeseafood.com",
    "www.henghengseafood.com",
    "www.ppnseafoodwishing.com",
    "siriratseafood.com",
    "www.sirinfarm.com",
}


def scrape_url(url: str) -> list[dict]:
    """Scrape a single product URL and return extracted rows."""
    domain = urlparse(url).netloc

    if domain == "supremeseafoods.net":
        return parse_supreme(url)

    if domain in WOOCOMMERCE_DOMAINS:
        soup = _soup(url)
        if soup is None:
            return []
        return parse_woocommerce(soup, url)

    log.warning("Unknown domain: %s — skipping %s", domain, url)
    return []


# ---------------------------------------------------------------------------
# Registry-driven scraping
# ---------------------------------------------------------------------------

def load_registry() -> list[dict]:
    """Load the product registry CSV (Google Sheet export)."""
    import pandas as pd

    df = pd.read_csv(REGISTRY_CSV)
    records = []
    for _, row in df.iterrows():
        link = str(row.get("link", "")).strip()
        if not link or link == "nan":
            continue
        records.append({
            "source": row["source"],
            "group_en": row["Group_Name_Eng"],
            "group_th": row["Group_Name_TH"],
            "link": link,
            "registry_option": str(row.get("option", "-")).strip(),
            "registry_weight": row.get("weight (kg)"),
            "registry_price": row.get("selling price (THB)"),
        })
    return records


def run_scrape(test_mode: bool = False) -> None:
    """Main scrape loop: visit each URL, extract prices, append to CSV."""
    registry = load_registry()
    today = date.today().isoformat()

    # Group by unique URL to avoid fetching the same page twice
    url_groups: dict[str, list[dict]] = {}
    for rec in registry:
        url_groups.setdefault(rec["link"], []).append(rec)

    urls = list(url_groups.keys())
    if test_mode:
        # Pick 1 URL per domain for testing
        seen_domains: set[str] = set()
        test_urls = []
        for u in urls:
            d = urlparse(u).netloc
            if d not in seen_domains:
                seen_domains.add(d)
                test_urls.append(u)
        urls = test_urls
        log.info("TEST MODE: scraping %d URLs (1 per domain)", len(urls))

    all_rows: list[dict] = []
    last_domain = ""

    for i, url in enumerate(urls):
        domain = urlparse(url).netloc

        # Rate limiting per domain
        if domain == last_domain:
            time.sleep(REQUEST_DELAY)
        last_domain = domain

        log.info("[%d/%d] Scraping %s", i + 1, len(urls), url[:80])

        scraped = scrape_url(url)
        if not scraped:
            log.warning("  No data extracted from %s", url)
            continue

        # Match scraped items back to registry metadata
        reg_items = url_groups[url]
        reg_first = reg_items[0]  # All share same source/group

        for item in scraped:
            row = {
                "scrape_date": today,
                "source": reg_first["source"],
                "item_name_website": item["item_name_website"],
                "group_en": reg_first["group_en"],
                "group_th": reg_first["group_th"],
                "option": item["option"],
                "weight_kg": "",
                "selling_price": item["selling_price"] if item["selling_price"] else "",
                "price_per_kg": "",
                "link": url,
            }

            # Try to match weight from registry for this option
            for reg in reg_items:
                if reg["registry_option"].strip() == item["option"].strip():
                    try:
                        w = float(str(reg["registry_weight"]).replace(",", ""))
                        row["weight_kg"] = w
                        if item["selling_price"] and w > 0:
                            row["price_per_kg"] = round(item["selling_price"] / w)
                    except (ValueError, TypeError):
                        pass
                    break

            all_rows.append(row)

        log.info("  Extracted %d items", len(scraped))

    # Write results
    if not all_rows:
        log.warning("No data scraped at all!")
        return

    file_exists = OUTPUT_CSV.exists() and OUTPUT_CSV.stat().st_size > 0

    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(all_rows)

    log.info(
        "Done! Appended %d rows to %s (date: %s)",
        len(all_rows), OUTPUT_CSV.name, today,
    )

    # Summary
    sources = set(r["source"] for r in all_rows)
    with_price = sum(1 for r in all_rows if r["selling_price"])
    log.info(
        "Sources scraped: %d/%d | Rows with price: %d/%d",
        len(sources), 7, with_price, len(all_rows),
    )

    # Trim history to keep only the last N scrape dates
    _trim_history(max_dates=30)


def _trim_history(max_dates: int = 30) -> None:
    """Keep only the most recent `max_dates` scrape dates in the output CSV."""
    if not OUTPUT_CSV.exists():
        return

    import pandas as pd

    df = pd.read_csv(OUTPUT_CSV)
    dates = sorted(df["scrape_date"].unique())

    if len(dates) <= max_dates:
        log.info("History has %d dates — no trimming needed (max %d)", len(dates), max_dates)
        return

    cutoff = dates[-max_dates]
    before = len(df)
    df = df[df["scrape_date"] >= cutoff]
    df.to_csv(OUTPUT_CSV, index=False)
    log.info(
        "Trimmed history: %d → %d rows (kept %d most recent dates, dropped before %s)",
        before, len(df), max_dates, cutoff,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape seafood prices")
    parser.add_argument("--test", action="store_true", help="Scrape 1 URL per site only")
    args = parser.parse_args()

    run_scrape(test_mode=args.test)
