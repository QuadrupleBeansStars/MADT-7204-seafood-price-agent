"""
Generate synthetic seafood price data for development and demo.

Produces realistic Bangkok market prices across multiple shops and SKUs.
Prices include daily variation to simulate real market conditions.

Usage:
    python data/scripts/generate_sample_data.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

# Bangkok seafood markets / shops
SHOPS = [
    "Talad Thai",
    "Or Tor Kor Market",
    "Makro Samut Prakan",
    "Thai Market Bangkapi",
    "Chatuchak Fish Market",
]

# SKU definitions: (sku, item_name, category, base_price_per_kg, unit)
SKUS = [
    ("SHRIMP-WHITE-L", "White Shrimp (Large)", "shrimp", 320, "kg"),
    ("SHRIMP-WHITE-M", "White Shrimp (Medium)", "shrimp", 260, "kg"),
    ("SHRIMP-TIGER-L", "Tiger Prawn (Large)", "shrimp", 480, "kg"),
    ("SHRIMP-TIGER-M", "Tiger Prawn (Medium)", "shrimp", 380, "kg"),
    ("FISH-SEABASS", "Sea Bass (Whole)", "fish", 220, "kg"),
    ("FISH-SNAPPER", "Red Snapper (Whole)", "fish", 280, "kg"),
    ("FISH-MACKEREL", "Mackerel (Whole)", "fish", 120, "kg"),
    ("FISH-SALMON-FILLET", "Salmon Fillet (Imported)", "fish", 650, "kg"),
    ("FISH-TILAPIA", "Tilapia (Whole)", "fish", 90, "kg"),
    ("SQUID-WHOLE-M", "Squid (Medium)", "squid", 200, "kg"),
    ("SQUID-WHOLE-L", "Squid (Large)", "squid", 260, "kg"),
    ("CRAB-MUD-L", "Mud Crab (Large)", "crab", 750, "kg"),
    ("CRAB-BLUE", "Blue Swimming Crab", "crab", 350, "kg"),
    ("MUSSEL-GREEN", "Green Mussel", "shellfish", 80, "kg"),
    ("CLAM-HARD", "Hard Shell Clam", "shellfish", 150, "kg"),
    ("OYSTER-FRESH", "Fresh Oyster", "shellfish", 420, "kg"),
]

# Shop-specific price multipliers (some shops are cheaper/pricier)
SHOP_MULTIPLIERS = {
    "Talad Thai": 0.90,            # Wholesale, cheapest
    "Or Tor Kor Market": 1.15,     # Premium market
    "Makro Samut Prakan": 0.95,    # Bulk retail
    "Thai Market Bangkapi": 1.00,  # Average
    "Chatuchak Fish Market": 1.05, # Slightly above average
}


def generate_data(num_days: int = 7, output_path: str | None = None) -> str:
    """Generate synthetic seafood price data."""
    if output_path is None:
        output_path = str(
            Path(__file__).parent.parent / "raw" / "seafood_prices_sample.csv"
        )

    today = date.today()
    start_date = today - timedelta(days=num_days - 1)

    rows = []
    for day_offset in range(num_days):
        current_date = start_date + timedelta(days=day_offset)

        for shop in SHOPS:
            shop_mult = SHOP_MULTIPLIERS[shop]

            for sku, item_name, category, base_price, unit in SKUS:
                # Daily price variation: ±8%
                daily_variation = random.uniform(0.92, 1.08)
                price = round(base_price * shop_mult * daily_variation, 1)

                # Availability: 90% chance available, lower for premium items
                avail_chance = 0.85 if base_price > 400 else 0.93
                available = random.random() < avail_chance

                rows.append({
                    "date": current_date.isoformat(),
                    "shop": shop,
                    "sku": sku,
                    "item_name": item_name,
                    "category": category,
                    "price_per_kg": price,
                    "unit": unit,
                    "available": available,
                })

    # Write CSV
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["date", "shop", "sku", "item_name", "category", "price_per_kg", "unit", "available"]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows → {output_path}")
    return output_path


if __name__ == "__main__":
    generate_data()
