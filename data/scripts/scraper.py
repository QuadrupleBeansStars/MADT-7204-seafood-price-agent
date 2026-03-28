"""
Seafood price scraper skeleton.

This script will be expanded to scrape real seafood prices from Bangkok markets.
Target sites/sources to be identified by the management team.

Usage:
    python data/scripts/scraper.py

TODO (Week 2):
    - Identify 3-5 real seafood price sources (websites, LINE groups, market APIs)
    - Implement scraping logic per source
    - Schedule daily runs (cron or manual)
    - Append results to data/raw/seafood_prices.csv
"""

import csv
from datetime import date
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "raw" / "seafood_prices.csv"

FIELDNAMES = [
    "date", "shop", "sku", "item_name", "category",
    "price_per_kg", "unit", "available",
]


def scrape_source_placeholder(source_name: str) -> list[dict]:
    """Placeholder for a single source scraper.

    Replace this with actual scraping logic per source.
    Each source should return a list of dicts matching FIELDNAMES.
    """
    # TODO: Implement real scraping
    # Example structure:
    # response = requests.get(source_url)
    # soup = BeautifulSoup(response.text, 'html.parser')
    # ... parse prices ...
    print(f"[PLACEHOLDER] Would scrape from: {source_name}")
    return []


def append_to_csv(rows: list[dict]) -> None:
    """Append scraped rows to the main CSV file."""
    file_exists = OUTPUT_PATH.exists()

    with open(OUTPUT_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    print(f"Appended {len(rows)} rows to {OUTPUT_PATH}")


def run_daily_scrape() -> None:
    """Run all scrapers and append results."""
    sources = [
        "Source 1 — TBD by management team",
        "Source 2 — TBD by management team",
        "Source 3 — TBD by management team",
    ]

    all_rows = []
    for source in sources:
        rows = scrape_source_placeholder(source)
        all_rows.extend(rows)

    if all_rows:
        append_to_csv(all_rows)
    else:
        print(f"[{date.today()}] No data scraped. Using sample data for development.")


if __name__ == "__main__":
    run_daily_scrape()
