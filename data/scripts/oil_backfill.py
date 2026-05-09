"""One-shot loader: import an EPPO historical retail-price spreadsheet
into data/raw/oil_prices.csv with source='eppo'.

Manual step:
  1. Download the latest historical retail price file from
     https://www.eppo.go.th/index.php/th/petroleum/price/historical-price
     (Excel; columns include date and per-litre prices for diesel, gasohol,
     etc.) and save somewhere local.
  2. Run: python data/scripts/oil_backfill.py /path/to/eppo.xlsx

Idempotent: rows with source='eppo' for an already-present (date, product)
pair are skipped.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

OUT_PATH = Path(__file__).resolve().parent.parent / "raw" / "oil_prices.csv"
SOURCE = "eppo"


def load_eppo_file(path: Path) -> pd.DataFrame:
    """EPPO files vary; we expect a 'date' column and one or more product
    columns (e.g. 'Diesel', 'Diesel B7', 'Gasohol 95'). Wide-form input,
    long-form output."""
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    if "date" not in {c.lower() for c in df.columns}:
        raise ValueError(f"EPPO file at {path} has no 'date' column")
    date_col = next(c for c in df.columns if c.lower() == "date")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    long = df.melt(id_vars=[date_col], var_name="product", value_name="thb_per_litre")
    long = long.dropna(subset=["thb_per_litre"])
    long["thb_per_litre"] = pd.to_numeric(long["thb_per_litre"], errors="coerce")
    long = long.dropna(subset=["thb_per_litre"])
    long = long.rename(columns={date_col: "date"})
    long["date"] = long["date"].dt.date.astype(str)
    return long[["date", "product", "thb_per_litre"]]


def existing_keys() -> set[tuple[str, str]]:
    if not OUT_PATH.exists():
        return set()
    with OUT_PATH.open("r", encoding="utf-8") as f:
        return {(r["date"], r["product"]) for r in csv.DictReader(f) if r["source"] == SOURCE}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: oil_backfill.py <path/to/eppo-file>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 1
    long = load_eppo_file(path)
    seen = existing_keys()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_file = not OUT_PATH.exists()
    written = 0
    with OUT_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "product", "thb_per_litre", "source"])
        if new_file:
            w.writeheader()
        for r in long.itertuples(index=False):
            if (r.date, r.product) in seen:
                continue
            w.writerow(
                {"date": r.date, "product": r.product, "thb_per_litre": r.thb_per_litre, "source": SOURCE}
            )
            written += 1
    print(f"[oil_backfill] wrote {written} rows from {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
