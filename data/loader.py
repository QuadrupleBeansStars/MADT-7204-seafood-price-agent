"""Unified data-loading layer for the Bangkok Seafood Price Advisor.

All tools and Streamlit pages import from here instead of hardcoding CSV
paths.  The module handles column renaming, category mapping, bilingual
names, and missing-price computation.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "raw"

# One-time Google-Sheet export (product registry)
REGISTRY_CSV = DATA_DIR / "เอเจ้นหาปลา - working sheet (tarn).csv"

# Accumulated scrape snapshots (populated by data/scripts/scraper.py)
SCRAPED_CSV = DATA_DIR / "seafood_prices.csv"

# ---------------------------------------------------------------------------
# Category mapping: Group_Name_Eng → broad category
# ---------------------------------------------------------------------------

CATEGORY_MAP: dict[str, str] = {
    # Shrimp / Prawn
    "Tiger Prawn": "shrimp",
    "Vannamei Shrimp": "shrimp",
    "Banana Prawn": "shrimp",
    "Prawn": "shrimp",
    "Mantish Shrimp": "shrimp",
    # Fish
    "Sea Bass": "fish",
    "Salmon": "fish",
    "Grouper": "fish",
    "Mullet": "fish",
    "Sand Whiting": "fish",
    "Spanish Mackerel": "fish",
    "Short-bodied Mackerel": "fish",
    "Snow Fish": "fish",
    "Black-banded Trevally": "fish",
    "Yellowtail": "fish",
    "Pomfret": "fish",
    "White Fish": "fish",
    "Barracuda": "fish",
    "Dory Fillet": "fish",
    "Minced Featherback Fish": "fish",
    "Leopard Coral Grouper": "fish",
    "Hamachi Kama": "fish",
    # Squid
    "Squid": "squid",
    # Crab
    "Crab Meat": "crab",
    "Blue Swimmer Crab": "crab",
    "Meder's Mangrove Crab": "crab",
    "Pickled Crab": "crab",
    # Shellfish
    "Oyster": "shellfish",
    "Scallops": "shellfish",
    "Spotted Babylon": "shellfish",
    "Mussels": "shellfish",
    "Baby Clams": "shellfish",
    "Hard Clams": "shellfish",
    "Blood Cockles": "shellfish",
    "Abalone": "shellfish",
    "Geoduck": "shellfish",
    "Wing Shells": "shellfish",
    "Scallop Mantle": "shellfish",
    "Honey Snail": "shellfish",
    "Jellyfish": "shellfish",
    "horseshoe crab": "shellfish",
}

CATEGORY_TH: dict[str, str] = {
    "shrimp": "กุ้ง",
    "fish": "ปลา",
    "squid": "หมึก",
    "crab": "ปู",
    "shellfish": "หอย/เปลือก",
    "other": "อื่นๆ",
}

VALID_CATEGORIES = set(CATEGORY_TH.keys()) - {"other"}

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _clean_numeric(series: pd.Series) -> pd.Series:
    """Convert a column that may contain '-', commas, or blanks to float."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip().replace({"-": None, "": None}),
        errors="coerce",
    )


def _load_registry() -> pd.DataFrame:
    """Load the one-time Google-Sheet export and normalise columns."""
    df = pd.read_csv(REGISTRY_CSV)

    df = df.rename(columns={
        "source": "source",
        "name from website": "item_name_website",
        "Group_Name_Eng": "group_en",
        "Group_Name_TH": "group_th",
        "option": "option",
        "weight (kg)": "weight_kg",
        "selling price (THB)": "selling_price",
        "price per kg (THB)": "price_per_kg",
        "link": "link",
    })

    # Clean numeric columns
    df["weight_kg"] = _clean_numeric(df["weight_kg"])
    df["selling_price"] = _clean_numeric(df["selling_price"])
    df["price_per_kg"] = _clean_numeric(df["price_per_kg"])

    # Compute missing price_per_kg where possible
    missing_ppkg = df["price_per_kg"].isna()
    can_compute = missing_ppkg & df["selling_price"].notna() & (df["weight_kg"] > 0)
    df.loc[can_compute, "price_per_kg"] = (
        df.loc[can_compute, "selling_price"] / df.loc[can_compute, "weight_kg"]
    ).round(0)

    # For items with selling_price but no weight (e.g. per-pack pricing),
    # keep selling_price as a reference — price_per_kg stays NaN.

    # Map categories
    df["category"] = df["group_en"].map(CATEGORY_MAP).fillna("other")
    unmapped = df.loc[df["category"] == "other", "group_en"].unique()
    if len(unmapped):
        logger.warning("Unmapped group names (defaulting to 'other'): %s", unmapped)

    df["category_th"] = df["category"].map(CATEGORY_TH)

    # Fill missing text columns
    df["option"] = df["option"].fillna("-")
    df["link"] = df["link"].fillna("")

    # Drop rows with zero or negative selling_price (data errors)
    df = df[df["selling_price"].notna() & (df["selling_price"] > 0)]

    return df.reset_index(drop=True)


def _prepare_scraped(scraped: pd.DataFrame) -> pd.DataFrame:
    """Normalise dtypes and add category columns to scraped data."""
    scraped["weight_kg"] = _clean_numeric(scraped["weight_kg"])
    scraped["selling_price"] = _clean_numeric(scraped["selling_price"])
    scraped["price_per_kg"] = _clean_numeric(scraped["price_per_kg"])
    scraped["option"] = scraped["option"].fillna("-")
    scraped["link"] = scraped["link"].fillna("")
    if "category" not in scraped.columns:
        scraped["category"] = scraped["group_en"].map(CATEGORY_MAP).fillna("other")
        scraped["category_th"] = scraped["category"].map(CATEGORY_TH)
    return scraped


def load_seafood_data() -> pd.DataFrame:
    """Return the best available seafood price DataFrame.

    Prefers accumulated scrape data (``data/raw/seafood_prices.csv``) when
    it exists.  For sources that failed to scrape (e.g. JS-only pricing),
    fills in missing products from the registry CSV so no shop disappears
    from the dataset.
    """
    if SCRAPED_CSV.exists() and SCRAPED_CSV.stat().st_size > 100:
        try:
            scraped = pd.read_csv(SCRAPED_CSV)
            if not scraped.empty:
                scraped = _prepare_scraped(scraped)

                # Fill gaps: add registry rows for sources missing from scrape
                registry = _load_registry()
                scraped_sources = set(scraped["source"].unique())
                registry_sources = set(registry["source"].unique())
                missing_sources = registry_sources - scraped_sources

                if missing_sources:
                    fallback = registry[registry["source"].isin(missing_sources)].copy()
                    logger.info(
                        "Filling %d rows from registry for sources missing in scrape: %s",
                        len(fallback), missing_sources,
                    )
                    scraped = pd.concat([scraped, fallback], ignore_index=True)

                return scraped
        except Exception:
            logger.warning("Failed to load scraped CSV, falling back to registry", exc_info=True)

    return _load_registry()


def has_historical_data() -> bool:
    """Return True if the scraped CSV has data from more than one date."""
    if not SCRAPED_CSV.exists():
        return False
    try:
        df = pd.read_csv(SCRAPED_CSV, usecols=["scrape_date"])
        return df["scrape_date"].nunique() > 1
    except Exception:
        return False
