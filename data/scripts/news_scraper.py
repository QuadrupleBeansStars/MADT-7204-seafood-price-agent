"""Daily RSS scraper for oil/energy news relevant to Thai seafood costs.

Pulls from three feeds, filters by keyword relevance, deduplicates by URL,
and appends to data/raw/oil_news.csv.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser

OUT_PATH = Path(__file__).resolve().parent.parent / "raw" / "oil_news.csv"
SENTINEL_PATH = Path(__file__).resolve().parent.parent / "raw" / ".oil_news_sentinel"

FEEDS = {
    "bangkokpost_business": "https://www.bangkokpost.com/rss/data/business.xml",
    "reuters_energy": "https://www.reutersagency.com/feed/?best-topics=energy&post_type=best",
    "krungthep_business": "https://www.bangkokbiznews.com/rss/feed/business",
}

# Oil-focused. Earlier broader terms ("energy", "logistics", "supply chain")
# pulled in noise — "energy" matched substring inside "emergency", and the
# rest caught generic business stories with no oil angle. Thai has no word
# boundaries so substring match is fine for Thai terms.
KEYWORDS_EN = {
    "oil", "diesel", "fuel", "petrol", "gasoline", "crude", "brent", "wti",
    "opec", "refinery", "refineries", "barrel", "barrels", "gasohol",
    "petroleum",
}
KEYWORDS_TH = {
    "น้ำมัน", "ดีเซล", "เบนซิน", "แก๊สโซฮอล์", "ปิโตรเลียม", "โอเปก", "ดิบ",
}
KEYWORDS = KEYWORDS_EN | KEYWORDS_TH  # kept for back-compat / tests

# Word-boundary regex for English so 'energy' inside 'emergency' doesn't match.
_EN_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in KEYWORDS_EN) + r")\b", re.I)

THAI_RE = re.compile(r"[฀-๿]")


def _detect_language(text: str) -> str:
    return "th" if THAI_RE.search(text or "") else "en"


def filter_relevant(entries: list) -> list[dict]:
    """Keep entries whose title or summary contains an oil-related term.

    English uses word-boundary matching; Thai uses substring.
    """
    kept = []
    for e in entries:
        haystack = (e.get("title") or "") + " " + (e.get("summary") or "")
        if _EN_RE.search(haystack) or any(kw in haystack for kw in KEYWORDS_TH):
            kept.append(e)
    return kept


def normalize_entry(entry, source: str) -> dict:
    title = (entry.get("title") or "").strip()
    summary = (entry.get("summary") or entry.get("description") or "").strip()
    summary = re.sub(r"<[^>]+>", "", summary)[:500]
    pub = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub is not None:
        dt = datetime(*pub[:6], tzinfo=timezone.utc).date().isoformat()
    else:
        dt = datetime.now(timezone.utc).date().isoformat()
    return {
        "date": dt,
        "source": source,
        "title": title,
        "url": (entry.get("link") or "").strip(),
        "snippet": summary,
        "language": _detect_language(title + " " + summary),
    }


def existing_urls(out_path: Path = OUT_PATH) -> set[str]:
    if not out_path.exists():
        return set()
    with out_path.open("r", encoding="utf-8") as f:
        return {row["url"] for row in csv.DictReader(f)}


def append_rows(rows: list[dict], out_path: Path = OUT_PATH) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists()
    n = 0
    with out_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["date", "source", "title", "url", "snippet", "language"]
        )
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow(r)
            n += 1
    return n


def main() -> int:
    seen = existing_urls()
    new_rows: list[dict] = []
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[news_scraper] {source} failed: {e}", file=sys.stderr)
            continue
        for entry in filter_relevant(feed.entries):
            row = normalize_entry(entry, source=source)
            if row["url"] and row["url"] not in seen:
                new_rows.append(row)
                seen.add(row["url"])
    n = append_rows(new_rows)
    SENTINEL_PATH.write_text(datetime.now(timezone.utc).isoformat())
    print(f"[news_scraper] appended {n} new articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
