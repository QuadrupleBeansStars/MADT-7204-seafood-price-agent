"""Unified data-loading layer for the Seafood Price Advisor.

All tools and Streamlit pages import from here instead of hardcoding CSV
paths.  The module handles column renaming, category mapping, bilingual
names, and missing-price computation.
"""

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "raw"

# One-time Google-Sheet export (product registry)
REGISTRY_CSV = DATA_DIR / "เอเจ้นหาปลา - working sheet (tarn).csv"

# Accumulated scrape snapshots (populated by data/scripts/scraper.py)
SCRAPED_CSV = DATA_DIR / "seafood_prices.csv"

# Talaad Thai wholesale market prices (populated by talaadthai_scraper.py)
TALAADTHAI_CSV = DATA_DIR / "talaadthai_prices.csv"

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


# --- Weight parser (option text → kg) -------------------------------------
#
# Many shops encode product weight in the option text rather than a separate
# column. Without this parser, those rows look like "pack-priced" items with
# no per-kg comparison possible, even though the data IS there. Examples:
#
#   "ปูม้า 500 กรัม"  ฿1500  → weight=0.5  → ฿3000/kg
#   "1.1 กิโลกรัม"    ฿300   → weight=1.1  → ฿273/kg
#   "L: 7-10 ตัวโล"   ฿400   → weight=1.0  → ฿400/kg  (sold per kilo by count)
#   "8-12 ตัว (กก)"   ฿500   → weight=1.0  → ฿500/kg  (parenthetical kg unit)
#
# Patterns we INTENTIONALLY skip — these are pure piece counts with no
# weight signal, so any conversion would be guesswork. Rows the parser
# can't resolve to a per-kg price are dropped by the loader (see below):
#   "3 ชิ้น/แพ็ค"            → no weight signal → dropped
#   "26-35 ตัว" (no unit)    → no weight signal → dropped

# Explicit grams: "500 กรัม", "280g", "500กรัม"
_RE_GRAMS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:กรัม|g)\b", re.IGNORECASE)

# Explicit kilograms: "1.1 กิโลกรัม", "1.3กิโล", "1 กก", "1 kg", "1.5kg"
_RE_KILOS = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:กิโลกรัม|กิโล|กก|kg)\b", re.IGNORECASE
)

# Implicit per-kg signals (no number to extract, just a marker):
#   "ตัวโล" — Thai for "pieces per kilo", canonical per-kg pricing
#   "(กก)" / "(kg)" — parenthetical unit suffix
_RE_PER_KG_MARKER = re.compile(r"ตัวโล|\(กก\)|\(kg\)", re.IGNORECASE)


def _parse_weight_kg_from_option(option: str) -> float | None:
    """Return weight in kg parsed from option text, or None if no signal.

    Order of precedence: explicit grams > explicit kg > per-kg marker.
    Grams comes first because options like "8-12 ตัว (280กรัม)" contain
    BOTH "(280กรัม)" and a piece count — the gram is the authoritative
    weight, not the implicit-per-kg fallback.
    """
    if not isinstance(option, str) or not option.strip() or option.strip() == "-":
        return None

    m = _RE_GRAMS.search(option)
    if m:
        try:
            return float(m.group(1).replace(",", ".")) / 1000.0
        except ValueError:
            pass

    m = _RE_KILOS.search(option)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass

    if _RE_PER_KG_MARKER.search(option):
        return 1.0

    return None


def _fill_weight_from_option(df: pd.DataFrame) -> pd.DataFrame:
    """Populate weight_kg from option text where the column is missing.

    Only fills NaN cells; never overwrites a value the source CSV already
    provided. Returns a NEW DataFrame — does not mutate the input — to
    follow the pandas convention that helpers return copies.
    """
    if "option" not in df.columns or "weight_kg" not in df.columns:
        return df
    out = df.copy()
    needs_fill = out["weight_kg"].isna()
    if not needs_fill.any():
        return out
    # Coerce explicitly to float so pandas doesn't warn about object→float
    # dtype assignment when most parsed values are None.
    parsed = out.loc[needs_fill, "option"].map(_parse_weight_kg_from_option)
    out.loc[needs_fill, "weight_kg"] = pd.to_numeric(parsed, errors="coerce")
    return out


def _compute_per_kg_from_weight(df: pd.DataFrame) -> pd.DataFrame:
    """Compute price_per_kg = selling_price / weight_kg where missing.

    Returns a NEW DataFrame; does not mutate the input.
    """
    # Coerce all three columns to numeric — callers may hand us hand-built
    # fixtures or partially-cleaned data where columns are object dtype.
    out = df.copy()
    out["price_per_kg"] = pd.to_numeric(out["price_per_kg"], errors="coerce")
    out["selling_price"] = pd.to_numeric(out["selling_price"], errors="coerce")
    out["weight_kg"] = pd.to_numeric(out["weight_kg"], errors="coerce")
    missing_ppkg = out["price_per_kg"].isna()
    can_compute = missing_ppkg & out["selling_price"].notna() & (out["weight_kg"] > 0)
    out.loc[can_compute, "price_per_kg"] = (
        (out.loc[can_compute, "selling_price"] / out.loc[can_compute, "weight_kg"])
        .round(0)
        .astype(float)
    )
    return out


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

    # Backfill weight_kg from option text where the source CSV omitted it,
    # then compute price_per_kg from weight + selling_price.
    df["option"] = df["option"].fillna("-")
    df = _fill_weight_from_option(df)
    df = _compute_per_kg_from_weight(df)

    # Drop pack-only rows (no per-kg price). Biz team found them confusing
    # in the comparison UI since they can't be compared apples-to-apples.
    df = df[df["price_per_kg"].notna() & (df["price_per_kg"] > 0)]

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


def load_talaadthai_benchmark() -> pd.DataFrame:
    """Talaad Thai wholesale market benchmark, one row per species.

    Talaad Thai is treated as the *market reference price* (ราคากลาง), not a
    retail supplier. Multiple item variants per species (e.g. small/medium/
    large size grades) are aggregated to a single price per ``group_en``:

        - ``price_per_kg``  mean of variants (the headline number)
        - ``price_min``     cheapest variant
        - ``price_max``     priciest variant
        - ``n_variants``    how many products were averaged
        - ``snapshot_date`` most-recent ``snapshot_date`` from the source
        - ``link``          link of the most-recent variant

    Returns an empty DataFrame when the CSV is missing or unreadable.
    """
    if not TALAADTHAI_CSV.exists() or TALAADTHAI_CSV.stat().st_size < 50:
        return pd.DataFrame()
    try:
        df = pd.read_csv(TALAADTHAI_CSV)
    except Exception:
        logger.warning("Failed to load talaadthai CSV", exc_info=True)
        return pd.DataFrame()
    if df.empty or "group_en" not in df.columns:
        return pd.DataFrame()

    df = df[df["price_per_kg"].notna() & df["group_en"].notna()].copy()
    if df.empty:
        return df

    if "snapshot_date" in df.columns:
        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce")
    else:
        df["snapshot_date"] = pd.NaT

    grouped = (
        df.sort_values("snapshot_date")
        .groupby("group_en")
        .agg(
            group_th=("group_th", "first"),
            price_per_kg=("price_per_kg", "mean"),
            price_min=("price_per_kg", "min"),
            price_max=("price_per_kg", "max"),
            n_variants=("price_per_kg", "size"),
            snapshot_date=("snapshot_date", "max"),
            link=("link", "last"),
            # All variant display names, joined for substring search by the
            # agent's benchmark tool. Users often query a child name
            # ("ปลาหมึกกล้วย") that doesn't appear in the parent group name
            # ("หมึก") — without this, the matcher misses the row entirely.
            item_names=("item_name_website", lambda s: " | ".join(sorted({str(x) for x in s.dropna()}))),
        )
        .reset_index()
    )
    return grouped


def _prepare_scraped(scraped: pd.DataFrame) -> pd.DataFrame:
    """Normalise dtypes and add category columns to scraped data."""
    scraped["weight_kg"] = _clean_numeric(scraped["weight_kg"])
    scraped["selling_price"] = _clean_numeric(scraped["selling_price"])
    scraped["price_per_kg"] = _clean_numeric(scraped["price_per_kg"])
    scraped["option"] = scraped["option"].fillna("-")
    scraped["link"] = scraped["link"].fillna("")
    # Backfill weight_kg from option text and compute per-kg pricing.
    # Scrapers rarely populate weight_kg, but the option text often
    # encodes it ("500 กรัม", "1.1 กิโลกรัม", "L: 7-10 ตัวโล").
    scraped = _fill_weight_from_option(scraped)
    scraped = _compute_per_kg_from_weight(scraped)
    # Drop pack-only rows (no per-kg price) so they don't reach the UI/agent.
    scraped = scraped[scraped["price_per_kg"].notna() & (scraped["price_per_kg"] > 0)]
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

                # Fill gaps from registry for sources that are either:
                # 1. Completely missing from scrape, or
                # 2. Present but with zero prices (e.g. JS-only sites like HENG HENG)
                registry = _load_registry()
                scraped_sources = set(scraped["source"].unique())
                registry_sources = set(registry["source"].unique())
                missing_sources = registry_sources - scraped_sources

                # Check for sources with 0 priced rows
                priceless_sources = set()
                for src in scraped_sources & registry_sources:
                    src_df = scraped[scraped["source"] == src]
                    if src_df["selling_price"].notna().sum() == 0:
                        priceless_sources.add(src)

                fallback_sources = missing_sources | priceless_sources

                if fallback_sources:
                    # Remove priceless scraped rows before replacing with registry
                    if priceless_sources:
                        scraped = scraped[~scraped["source"].isin(priceless_sources)]
                    fallback = registry[registry["source"].isin(fallback_sources)].copy()
                    logger.info(
                        "Filling %d rows from registry for sources: %s",
                        len(fallback), fallback_sources,
                    )
                    scraped = pd.concat([scraped, fallback], ignore_index=True)

                # Merge in synthetic demo shops
                try:
                    from data.mock_shops import generate_mock_rows
                    mock_rows = generate_mock_rows(scraped)
                    if not mock_rows.empty:
                        scraped = pd.concat([scraped, mock_rows], ignore_index=True)
                except Exception:
                    logger.warning("Could not generate mock shop rows", exc_info=True)

                # NOTE: Talaad Thai is intentionally NOT merged here. It is
                # the market benchmark (ราคากลาง), surfaced separately via
                # ``load_talaadthai_benchmark()``.

                return scraped
        except Exception:
            logger.warning("Failed to load scraped CSV, falling back to registry", exc_info=True)

    return _load_registry()


def latest_per_shop_item(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse historical scrape rows to the latest per (source, group_en, option).

    The scraped CSV accumulates one row per shop+item+option per day. Code
    that answers "what's the price *now*" — agent tools, dashboard charts,
    shop profile stats — must dedupe to today's snapshot. Otherwise the
    same shop+item appears N times (once per scrape day) and aggregations
    silently sum/stack across history. The dashboard bar chart was
    rendering bars at ฿15k/kg because Plotly stacked 15+ days of ฿400/kg
    rows for the same shop+item — the original production bug we now fix
    in one shared place instead of three.

    Rows without a parseable ``scrape_date`` (e.g. registry fallback) are
    kept as-is; they're treated as the "latest" by default since they
    have no timestamp to age out.
    """
    if df.empty or "scrape_date" not in df.columns:
        return df
    work = df.copy()
    work["_dt"] = pd.to_datetime(work["scrape_date"], errors="coerce")
    # Sort so most-recent rows come last; drop_duplicates(keep="last") then
    # keeps the freshest per shop+item+option. NaT sorts first, so dated
    # rows correctly win over timestamp-less ones.
    work = work.sort_values("_dt", na_position="first")
    work = work.drop_duplicates(
        subset=["source", "group_en", "option"], keep="last"
    )
    return work.drop(columns="_dt")


def has_historical_data() -> bool:
    """Return True if the scraped CSV has data from more than one date."""
    if not SCRAPED_CSV.exists():
        return False
    try:
        df = pd.read_csv(SCRAPED_CSV, usecols=["scrape_date"])
        return df["scrape_date"].nunique() > 1
    except Exception:
        return False
