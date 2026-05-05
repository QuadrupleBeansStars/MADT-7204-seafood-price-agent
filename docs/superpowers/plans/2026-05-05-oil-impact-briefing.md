# Oil Impact Briefing & Correlation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily oil-price + oil-news pipeline, an "Oil Impact Briefing" agent feature, an oil↔seafood correlation page, and oil-aware chat responses.

**Architecture:** Two new daily scrapers (`oil_scraper.py`, `news_scraper.py`) plus a one-shot EPPO backfill produce CSVs under `data/raw/`. Two new agent tools (`get_oil_context`, `generate_oil_briefing`) read those CSVs and the existing seafood data. The system prompt gains a one-line oil snapshot. Streamlit gains a briefing modal in the AI Chat page and a new Market Insights page with a dual-axis chart and lag-correlation table. Briefings cached for 6h in SQLite.

**Tech Stack:** Python 3.11, BeautifulSoup4, requests, feedparser, pandas, sqlite3 (stdlib), plotly, streamlit, langchain-core (`@tool`), langchain-anthropic, pytest.

**Spec:** `docs/superpowers/specs/2026-05-05-oil-impact-design.md`

---

## File map

**Create:**
- `data/scripts/oil_scraper.py` — daily Thaioil HTML scrape
- `data/scripts/oil_backfill.py` — one-shot EPPO historical loader
- `data/scripts/news_scraper.py` — daily RSS scrape
- `data/oil_loader.py` — read helpers for oil_prices.csv and oil_news.csv
- `data/oil_correlation.py` — pure stats: pct change, lag correlation
- `agent/tools/oil_context.py` — `get_oil_context` tool + `oil_snapshot_line()` helper
- `agent/tools/oil_briefing.py` — `generate_oil_briefing` tool + cache
- `app/pages/market_insights.py` — correlation page
- `docs/oil-feature-limitations.md` — limitations doc
- `tests/test_oil_scraper.py`
- `tests/test_oil_correlation.py`
- `tests/test_news_scraper.py`
- `tests/test_oil_context.py`
- `tests/test_oil_briefing.py`
- `tests/fixtures/thaioil_sample.html`
- `tests/fixtures/rss_sample.xml`

**Modify:**
- `agent/tools/__init__.py` — export new tools, extend `ALL_TOOLS`
- `agent/main.py` — inject oil snapshot into system prompt at request time
- `app/pages/chat.py` — add "Oil Impact Briefing" button + `st.dialog`
- `requirements.txt` — add `feedparser`, `plotly`
- `.github/workflows/scrape.yml` — also run oil + news scrapers

**Out of repo (manual):**
- `data/raw/oil_prices.csv` — seeded by EPPO backfill (Task 11)

---

## Task 1: Oil price scraper (TDD with HTML fixture)

**Files:**
- Create: `data/scripts/oil_scraper.py`
- Create: `tests/test_oil_scraper.py`
- Create: `tests/fixtures/thaioil_sample.html`

- [ ] **Step 1.1: Save a representative HTML fixture**

Save the following minimal but realistic fixture to `tests/fixtures/thaioil_sample.html` (mirrors the structure the user verified — `<img alt="...">` followed by `<p class="oil-price">N</p>`):

```html
<!doctype html>
<html><body>
<div class="oil-prices">
  <img decoding="async" alt="Diesel" src="https://example/diesel.webp" class="lazyloaded">
  <p class="oil-price">40.80</p>
  <img decoding="async" alt="Diesel B20" src="https://example/diesel-b20.webp" class="lazyloaded">
  <p class="oil-price">33.80</p>
  <img decoding="async" alt="Gasohol 95" src="https://example/gasohol-95.webp" class="lazyloaded">
  <p class="oil-price">42.93</p>
</div>
</body></html>
```

- [ ] **Step 1.2: Write failing parser tests**

Create `tests/test_oil_scraper.py`:

```python
from pathlib import Path
from data.scripts.oil_scraper import parse_oil_prices

FIXTURE = Path(__file__).parent / "fixtures" / "thaioil_sample.html"


def test_parse_pairs_alt_with_price():
    html = FIXTURE.read_text()
    rows = parse_oil_prices(html)
    assert {"Diesel": 40.80, "Diesel B20": 33.80, "Gasohol 95": 42.93} == {
        r["product"]: r["thb_per_litre"] for r in rows
    }


def test_parse_returns_list_of_dicts_with_expected_keys():
    rows = parse_oil_prices(FIXTURE.read_text())
    assert all(set(r.keys()) == {"product", "thb_per_litre"} for r in rows)


def test_parse_raises_on_missing_prices():
    import pytest
    with pytest.raises(ValueError, match="no oil prices found"):
        parse_oil_prices("<html><body>nothing here</body></html>")


def test_parse_raises_on_mismatch_between_imgs_and_prices():
    import pytest
    html = '<p class="oil-price">10.0</p><p class="oil-price">20.0</p>'
    with pytest.raises(ValueError, match="no oil prices found"):
        parse_oil_prices(html)
```

- [ ] **Step 1.3: Run tests, verify they fail**

```bash
conda activate MADT
pytest tests/test_oil_scraper.py -v
```

Expected: 4 failures, all with "ModuleNotFoundError: No module named 'data.scripts.oil_scraper'".

- [ ] **Step 1.4: Implement `parse_oil_prices`**

Create `data/scripts/oil_scraper.py`:

```python
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
        # Find the nearest preceding <img alt="...">
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
```

- [ ] **Step 1.5: Run parser tests, verify pass**

```bash
pytest tests/test_oil_scraper.py -v
```

Expected: 4 passed.

- [ ] **Step 1.6: Add idempotency tests**

Append to `tests/test_oil_scraper.py`:

```python
def test_already_scraped_today_false_when_file_missing(tmp_path):
    from data.scripts.oil_scraper import already_scraped_today
    from datetime import date
    assert already_scraped_today(date(2026, 5, 5), tmp_path / "missing.csv") is False


def test_append_then_already_scraped_returns_true(tmp_path):
    from data.scripts.oil_scraper import append_rows, already_scraped_today
    from datetime import date
    p = tmp_path / "oil.csv"
    append_rows([{"product": "Diesel", "thb_per_litre": 40.0}], date(2026, 5, 5), p)
    assert already_scraped_today(date(2026, 5, 5), p) is True
    assert already_scraped_today(date(2026, 5, 6), p) is False
```

Run:
```bash
pytest tests/test_oil_scraper.py -v
```
Expected: 6 passed.

- [ ] **Step 1.7: Commit**

```bash
git add data/scripts/oil_scraper.py tests/test_oil_scraper.py tests/fixtures/thaioil_sample.html
git commit -m "feat: daily Thaioil price scraper with HTML-fixture tests"
```

---

## Task 2: Lag correlation utility (pure stats, TDD)

**Files:**
- Create: `data/oil_correlation.py`
- Create: `tests/test_oil_correlation.py`

- [ ] **Step 2.1: Write failing tests with synthetic data**

Create `tests/test_oil_correlation.py`:

```python
import math
import pandas as pd
from data.oil_correlation import lag_correlation, pct_change, MIN_SAMPLE


def _series(values, start="2026-01-01"):
    idx = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(values, index=idx)


def test_lag_correlation_perfect_lag_14():
    """Seafood lags oil by exactly 14 days → r at lag 14 should be ~1.0."""
    oil = _series([float(i) for i in range(60)])
    seafood = _series([float(i) for i in range(60)], start="2026-01-15")  # 14d later
    result = lag_correlation(oil, seafood, lags=[0, 7, 14, 21])
    assert result[14] is not None and result[14] > 0.99
    assert result[0] is not None and result[0] < 0.5


def test_lag_correlation_returns_none_when_below_min_sample():
    oil = _series([1.0, 2.0, 3.0])
    seafood = _series([1.0, 2.0, 3.0])
    result = lag_correlation(oil, seafood, lags=[0])
    assert result[0] is None


def test_lag_correlation_handles_missing_dates():
    oil = _series([float(i) for i in range(MIN_SAMPLE + 10)])
    seafood = oil.iloc[::2]  # half the dates missing
    result = lag_correlation(oil, seafood, lags=[0])
    # Overlap after alignment is < MIN_SAMPLE, so None expected
    assert result[0] is None


def test_pct_change_basic():
    s = _series([100.0] * 5 + [110.0])
    assert math.isclose(pct_change(s, days=5), 10.0, abs_tol=0.01)


def test_pct_change_returns_none_on_short_series():
    s = _series([100.0])
    assert pct_change(s, days=7) is None
```

- [ ] **Step 2.2: Run, verify fail**

```bash
pytest tests/test_oil_correlation.py -v
```

Expected: 5 failures, ModuleNotFoundError.

- [ ] **Step 2.3: Implement**

Create `data/oil_correlation.py`:

```python
"""Pure stats helpers for oil ↔ seafood analysis.

No I/O, no LLM — just pandas. Easy to test, easy to reason about.
"""

from __future__ import annotations

import pandas as pd

MIN_SAMPLE = 30  # days of overlapping data required before we report r


def pct_change(series: pd.Series, days: int) -> float | None:
    """Percent change from N days ago to most recent point.

    Returns None if the series is too short or value N+1 days back is NaN.
    """
    s = series.dropna().sort_index()
    if len(s) <= days:
        return None
    latest = s.iloc[-1]
    past = s.iloc[-(days + 1)]
    if past == 0:
        return None
    return float((latest - past) / past * 100.0)


def lag_correlation(
    oil: pd.Series,
    seafood: pd.Series,
    lags: list[int],
) -> dict[int, float | None]:
    """Pearson r between oil and seafood, with seafood shifted by N days.

    A positive lag means seafood reacts to oil N days later.
    Returns {lag: r or None}. None means overlap < MIN_SAMPLE.
    Both series must be daily-indexed (DatetimeIndex).
    """
    oil = oil.dropna().sort_index()
    seafood = seafood.dropna().sort_index()
    out: dict[int, float | None] = {}
    for lag in lags:
        shifted = seafood.shift(-lag).dropna() if lag != 0 else seafood
        joined = pd.concat([oil, shifted], axis=1, join="inner").dropna()
        if len(joined) < MIN_SAMPLE:
            out[lag] = None
            continue
        r = joined.iloc[:, 0].corr(joined.iloc[:, 1])
        out[lag] = float(r) if pd.notna(r) else None
    return out
```

- [ ] **Step 2.4: Run, verify pass**

```bash
pytest tests/test_oil_correlation.py -v
```

Expected: 5 passed.

- [ ] **Step 2.5: Commit**

```bash
git add data/oil_correlation.py tests/test_oil_correlation.py
git commit -m "feat: lag-correlation and pct-change helpers with tests"
```

---

## Task 3: Oil data loader

**Files:**
- Create: `data/oil_loader.py`

- [ ] **Step 3.1: Implement loader (no test — thin pandas wrapper)**

Create `data/oil_loader.py`:

```python
"""Read helpers for oil_prices.csv and oil_news.csv.

Kept thin so the agent tools and Streamlit pages share one source of truth.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

OIL_PRICES_PATH = Path(__file__).resolve().parent / "raw" / "oil_prices.csv"
OIL_NEWS_PATH = Path(__file__).resolve().parent / "raw" / "oil_news.csv"


def load_oil_prices() -> pd.DataFrame:
    """Return long-form DataFrame: date (datetime), product, thb_per_litre, source."""
    if not OIL_PRICES_PATH.exists():
        return pd.DataFrame(columns=["date", "product", "thb_per_litre", "source"])
    df = pd.read_csv(OIL_PRICES_PATH, parse_dates=["date"])
    return df


def diesel_series() -> pd.Series:
    """Daily diesel price series indexed by date. Picks 'Diesel' product."""
    df = load_oil_prices()
    diesel = df[df["product"].str.casefold() == "diesel"]
    if diesel.empty:
        return pd.Series(dtype=float)
    daily = diesel.groupby("date")["thb_per_litre"].mean().sort_index()
    return daily


def load_oil_news(days: int) -> pd.DataFrame:
    """Return news articles within the last N days."""
    if not OIL_NEWS_PATH.exists():
        return pd.DataFrame(columns=["date", "source", "title", "url", "snippet", "language"])
    df = pd.read_csv(OIL_NEWS_PATH, parse_dates=["date"])
    cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
    return df[df["date"] >= cutoff].sort_values("date", ascending=False)
```

- [ ] **Step 3.2: Commit**

```bash
git add data/oil_loader.py
git commit -m "feat: oil data loader (prices + news)"
```

---

## Task 4: News RSS scraper (TDD with feed fixture)

**Files:**
- Create: `data/scripts/news_scraper.py`
- Create: `tests/test_news_scraper.py`
- Create: `tests/fixtures/rss_sample.xml`
- Modify: `requirements.txt`

- [ ] **Step 4.1: Add `feedparser` to requirements**

Append to `requirements.txt`:
```
feedparser>=6.0
plotly>=5.20
```

- [ ] **Step 4.2: Install**

```bash
conda activate MADT
pip install feedparser plotly
```

- [ ] **Step 4.3: Save RSS fixture**

`tests/fixtures/rss_sample.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test Feed</title>
  <item>
    <title>Diesel prices rise as global oil climbs</title>
    <link>https://example.com/a</link>
    <description>Thai diesel rose 0.5 THB/L this week amid Brent gains.</description>
    <pubDate>Mon, 04 May 2026 10:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Football match preview</title>
    <link>https://example.com/b</link>
    <description>Bangkok United faces Buriram tonight.</description>
    <pubDate>Mon, 04 May 2026 11:00:00 +0000</pubDate>
  </item>
  <item>
    <title>น้ำมันดีเซลขึ้นราคาอีกรอบ</title>
    <link>https://example.com/c</link>
    <description>กระทบต้นทุนขนส่งและอาหารทะเล</description>
    <pubDate>Mon, 04 May 2026 12:00:00 +0000</pubDate>
  </item>
</channel></rss>
```

- [ ] **Step 4.4: Write failing tests**

Create `tests/test_news_scraper.py`:

```python
from pathlib import Path
import feedparser

from data.scripts.news_scraper import filter_relevant, normalize_entry, KEYWORDS

FIXTURE = Path(__file__).parent / "fixtures" / "rss_sample.xml"


def test_filter_keeps_oil_related_items():
    feed = feedparser.parse(str(FIXTURE))
    kept = filter_relevant(feed.entries)
    titles = [e["title"] for e in kept]
    assert "Diesel prices rise as global oil climbs" in titles
    assert "น้ำมันดีเซลขึ้นราคาอีกรอบ" in titles


def test_filter_drops_unrelated_items():
    feed = feedparser.parse(str(FIXTURE))
    kept = filter_relevant(feed.entries)
    titles = [e["title"] for e in kept]
    assert "Football match preview" not in titles


def test_normalize_entry_returns_expected_columns():
    feed = feedparser.parse(str(FIXTURE))
    row = normalize_entry(feed.entries[0], source="testfeed")
    assert set(row.keys()) == {"date", "source", "title", "url", "snippet", "language"}
    assert row["url"] == "https://example.com/a"
    assert row["language"] == "en"


def test_normalize_detects_thai_language():
    feed = feedparser.parse(str(FIXTURE))
    row = normalize_entry(feed.entries[2], source="testfeed")
    assert row["language"] == "th"


def test_keywords_include_thai_and_english():
    assert "diesel" in KEYWORDS
    assert "น้ำมัน" in KEYWORDS
```

- [ ] **Step 4.5: Run, verify fail**

```bash
pytest tests/test_news_scraper.py -v
```
Expected: 5 failures, ModuleNotFoundError.

- [ ] **Step 4.6: Implement scraper**

Create `data/scripts/news_scraper.py`:

```python
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

KEYWORDS = {
    "oil", "diesel", "fuel", "petrol", "gasoline", "energy", "subsidy",
    "fishing", "seafood", "logistics", "supply chain",
    "น้ำมัน", "ดีเซล", "พลังงาน", "ประมง", "อาหารทะเล", "ขนส่ง", "อุดหนุน",
}

THAI_RE = re.compile(r"[฀-๿]")


def _detect_language(text: str) -> str:
    return "th" if THAI_RE.search(text or "") else "en"


def filter_relevant(entries: list) -> list[dict]:
    """Keep entries whose title or summary contains any KEYWORDS term."""
    kept = []
    for e in entries:
        haystack = ((e.get("title") or "") + " " + (e.get("summary") or "")).casefold()
        if any(kw.casefold() in haystack for kw in KEYWORDS):
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
```

- [ ] **Step 4.7: Run, verify pass**

```bash
pytest tests/test_news_scraper.py -v
```
Expected: 5 passed.

- [ ] **Step 4.8: Commit**

```bash
git add data/scripts/news_scraper.py tests/test_news_scraper.py tests/fixtures/rss_sample.xml requirements.txt
git commit -m "feat: daily RSS news scraper for oil/energy items"
```

---

## Task 5: `get_oil_context` agent tool

**Files:**
- Create: `agent/tools/oil_context.py`
- Create: `tests/test_oil_context.py`

- [ ] **Step 5.1: Write failing tests**

Create `tests/test_oil_context.py`:

```python
import pandas as pd
import pytest

from agent.tools import oil_context as mod


@pytest.fixture
def fake_diesel(monkeypatch):
    idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=60, freq="D")
    series = pd.Series([30.0 + 0.05 * i for i in range(60)], index=idx)
    monkeypatch.setattr(mod, "diesel_series", lambda: series)
    return series


def test_oil_snapshot_line_returns_human_readable(fake_diesel):
    line = mod.oil_snapshot_line()
    assert "Diesel" in line
    assert "THB/L" in line
    assert "%" in line


def test_oil_snapshot_line_when_no_data(monkeypatch):
    monkeypatch.setattr(mod, "diesel_series", lambda: pd.Series(dtype=float))
    assert mod.oil_snapshot_line() == ""


def test_get_oil_context_invokable_without_species(fake_diesel):
    out = mod.get_oil_context.invoke({})
    assert "diesel_thb_per_l" in out
    assert out["lag_correlation"] is None
    assert out["change_7d_pct"] is not None


def test_get_oil_context_with_unknown_species_returns_none_correlation(fake_diesel, monkeypatch):
    monkeypatch.setattr(mod, "_seafood_daily_avg", lambda species: pd.Series(dtype=float))
    out = mod.get_oil_context.invoke({"species": "unicornfish"})
    assert out["lag_correlation"] is None
    assert out["n_days_overlap"] == 0
```

- [ ] **Step 5.2: Run, verify fail**

```bash
pytest tests/test_oil_context.py -v
```
Expected: 4 failures.

- [ ] **Step 5.3: Implement**

Create `agent/tools/oil_context.py`:

```python
"""`get_oil_context` agent tool + `oil_snapshot_line` helper for system prompt.

The tool returns current diesel price, recent percent changes, and (when a
species is given and there is enough overlap) lagged correlation with the
species' average price.
"""

from __future__ import annotations

import pandas as pd
from langchain_core.tools import tool

from data.loader import load_seafood_data
from data.oil_correlation import MIN_SAMPLE, lag_correlation, pct_change
from data.oil_loader import diesel_series

LAGS = [0, 7, 14, 21, 28]


def _seafood_daily_avg(species: str) -> pd.Series:
    """Daily mean price-per-kg for a species (matched against group_en)."""
    df = load_seafood_data()
    if "scrape_date" not in df.columns:
        return pd.Series(dtype=float)
    mask = df["group_en"].str.contains(species, case=False, na=False) | df[
        "group_th"
    ].str.contains(species, case=False, na=False)
    sub = df[mask & df["price_per_kg"].notna()].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    sub["scrape_date"] = pd.to_datetime(sub["scrape_date"], errors="coerce")
    sub = sub.dropna(subset=["scrape_date"])
    return sub.groupby("scrape_date")["price_per_kg"].mean().sort_index()


def oil_snapshot_line() -> str:
    """One-line snapshot for system prompt injection. Empty string if no data."""
    s = diesel_series()
    if s.empty:
        return ""
    latest = s.iloc[-1]
    c7 = pct_change(s, 7)
    c30 = pct_change(s, 30)
    parts = [f"Diesel {latest:.2f} THB/L"]
    if c7 is not None:
        parts.append(f"{c7:+.1f}% 7d")
    if c30 is not None:
        parts.append(f"{c30:+.1f}% 30d")
    return f"Current oil context: {parts[0]} (" + ", ".join(parts[1:]) + ")."


@tool
def get_oil_context(species: str | None = None) -> dict:
    """Return current Thai diesel price, recent change, and (if species given)
    lagged correlation with that species' avg price.

    Use this whenever the user asks why prices may move, or when answering
    about a specific species and oil moves are large enough to be relevant.

    Args:
        species: Optional seafood species (English or Thai partial match).
                 When provided and enough overlapping data exists (>= 30 days),
                 the response includes Pearson r at lags 0/7/14/21/28 days.
    """
    s = diesel_series()
    out: dict = {
        "diesel_thb_per_l": float(s.iloc[-1]) if not s.empty else None,
        "change_7d_pct": pct_change(s, 7),
        "change_30d_pct": pct_change(s, 30),
        "lag_correlation": None,
        "n_days_overlap": 0,
    }
    if species:
        seafood = _seafood_daily_avg(species)
        joined = pd.concat([s, seafood], axis=1, join="inner").dropna()
        out["n_days_overlap"] = int(len(joined))
        if len(joined) >= MIN_SAMPLE:
            corr = lag_correlation(s, seafood, LAGS)
            out["lag_correlation"] = {str(k): v for k, v in corr.items()}
    return out
```

- [ ] **Step 5.4: Run, verify pass**

```bash
pytest tests/test_oil_context.py -v
```
Expected: 4 passed.

- [ ] **Step 5.5: Commit**

```bash
git add agent/tools/oil_context.py tests/test_oil_context.py
git commit -m "feat: get_oil_context tool with snapshot helper"
```

---

## Task 6: `generate_oil_briefing` tool with cache

**Files:**
- Create: `agent/tools/oil_briefing.py`
- Create: `tests/test_oil_briefing.py`

- [ ] **Step 6.1: Write failing tests (cache logic, then LLM stub)**

Create `tests/test_oil_briefing.py`:

```python
import sqlite3
import pandas as pd
import pytest

from agent.tools import oil_briefing as mod


@pytest.fixture
def cache_db(tmp_path, monkeypatch):
    p = tmp_path / "briefing_cache.sqlite"
    monkeypatch.setattr(mod, "CACHE_PATH", p)
    monkeypatch.setattr(mod, "SENTINEL_PATH", tmp_path / ".sentinel")
    mod._init_cache()
    return p


@pytest.fixture
def fake_news(monkeypatch):
    df = pd.DataFrame([
        {"date": pd.Timestamp("2026-05-04"), "source": "bkkpost",
         "title": "Diesel rises", "url": "https://x/1",
         "snippet": "Thai diesel up", "language": "en"},
        {"date": pd.Timestamp("2026-05-03"), "source": "reuters",
         "title": "Brent climbs", "url": "https://x/2",
         "snippet": "Global oil higher", "language": "en"},
    ])
    monkeypatch.setattr(mod, "load_oil_news", lambda days: df)
    return df


def test_cache_miss_then_hit_returns_same_value(cache_db, fake_news, monkeypatch):
    calls = {"n": 0}

    def fake_llm(prompt: str) -> str:
        calls["n"] += 1
        return "- Diesel up: https://x/1\n- Brent climbs: https://x/2"

    monkeypatch.setattr(mod, "_summarize_with_llm", fake_llm)
    a = mod.generate_oil_briefing.invoke({"period": "weekly", "language": "en"})
    b = mod.generate_oil_briefing.invoke({"period": "weekly", "language": "en"})
    assert a == b
    assert calls["n"] == 1  # second call hit cache


def test_briefing_contains_source_links(cache_db, fake_news, monkeypatch):
    monkeypatch.setattr(
        mod,
        "_summarize_with_llm",
        lambda p: "- Item: https://x/1",
    )
    out = mod.generate_oil_briefing.invoke({"period": "weekly", "language": "en"})
    assert "https://x/1" in out


def test_no_news_returns_friendly_message(cache_db, monkeypatch):
    monkeypatch.setattr(mod, "load_oil_news", lambda days: pd.DataFrame())
    out = mod.generate_oil_briefing.invoke({"period": "weekly", "language": "en"})
    assert "no recent" in out.lower() or "no oil-related" in out.lower()


def test_invalid_period_raises(cache_db):
    with pytest.raises(ValueError):
        mod.generate_oil_briefing.invoke({"period": "yearly", "language": "en"})


def test_sentinel_invalidates_cache(cache_db, fake_news, monkeypatch):
    import time
    calls = {"n": 0}
    def fake_llm(p):
        calls["n"] += 1
        return "- x: https://x/1"
    monkeypatch.setattr(mod, "_summarize_with_llm", fake_llm)
    mod.generate_oil_briefing.invoke({"period": "weekly", "language": "en"})
    time.sleep(0.01)
    mod.SENTINEL_PATH.write_text("new-news")
    mod.generate_oil_briefing.invoke({"period": "weekly", "language": "en"})
    assert calls["n"] == 2
```

- [ ] **Step 6.2: Run, verify fail**

```bash
pytest tests/test_oil_briefing.py -v
```
Expected: 5 failures.

- [ ] **Step 6.3: Implement**

Create `agent/tools/oil_briefing.py`:

```python
"""`generate_oil_briefing` tool — cached LLM summary of oil news.

Cache: SQLite, keyed by (period, language), 6h TTL, also invalidated when
the news scraper writes a fresh sentinel file.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pandas as pd
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from data.oil_loader import load_oil_news

CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "briefing_cache.sqlite"
SENTINEL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / ".oil_news_sentinel"
TTL_SECONDS = 6 * 3600
PERIODS = {"weekly": 7, "monthly": 30}


def _init_cache(path: Path | None = None) -> None:
    p = path or CACHE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS briefings ("
            "  period TEXT NOT NULL, language TEXT NOT NULL,"
            "  generated_at REAL NOT NULL, markdown TEXT NOT NULL,"
            "  PRIMARY KEY (period, language))"
        )


def _sentinel_mtime() -> float:
    return SENTINEL_PATH.stat().st_mtime if SENTINEL_PATH.exists() else 0.0


def _cache_get(period: str, language: str) -> str | None:
    _init_cache()
    with sqlite3.connect(CACHE_PATH) as conn:
        row = conn.execute(
            "SELECT generated_at, markdown FROM briefings WHERE period=? AND language=?",
            (period, language),
        ).fetchone()
    if row is None:
        return None
    generated_at, markdown = row
    if time.time() - generated_at > TTL_SECONDS:
        return None
    if generated_at < _sentinel_mtime():
        return None
    return markdown


def _cache_put(period: str, language: str, markdown: str) -> None:
    _init_cache()
    with sqlite3.connect(CACHE_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO briefings(period, language, generated_at, markdown)"
            " VALUES (?, ?, ?, ?)",
            (period, language, time.time(), markdown),
        )


def _build_prompt(news: pd.DataFrame, period: str, language: str) -> str:
    lang_label = "Thai (ภาษาไทย)" if language == "th" else "English"
    items = "\n".join(
        f"- [{r.source}] {r.title} ({r.url})\n  {r.snippet}"
        for r in news.itertuples()
    )
    return (
        f"You are an analyst summarizing recent oil/energy news for Thai seafood "
        f"buyers, restaurant owners, and suppliers.\n\n"
        f"Write the briefing in {lang_label}.\n"
        f"Period: last {PERIODS[period]} days.\n\n"
        f"Articles:\n{items}\n\n"
        f"Output rules:\n"
        f"- Maximum 5 bullet points.\n"
        f"- Each bullet must include the source URL inline.\n"
        f"- After bullets, add a short 'Possible seafood cost impact' paragraph.\n"
        f"- Then add a 'Practical actions' section with 2-3 concrete suggestions.\n"
        f"- Avoid unsupported claims; mention uncertainty when data is unclear.\n"
        f"- Use simple business language.\n"
    )


def _summarize_with_llm(prompt: str) -> str:
    """Call Claude. Patched in tests."""
    llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0)
    return llm.invoke([HumanMessage(content=prompt)]).content


@tool
def generate_oil_briefing(period: str, language: str) -> str:
    """Generate (or fetch from cache) a briefing of recent oil/energy news
    that may affect Thai seafood costs.

    Args:
        period: 'weekly' (last 7 days) or 'monthly' (last 30 days).
        language: 'th' or 'en'.
    """
    if period not in PERIODS:
        raise ValueError(f"period must be 'weekly' or 'monthly', got {period!r}")
    if language not in ("th", "en"):
        raise ValueError(f"language must be 'th' or 'en', got {language!r}")

    cached = _cache_get(period, language)
    if cached is not None:
        return cached

    news = load_oil_news(days=PERIODS[period])
    if news is None or news.empty:
        msg = (
            "No recent oil-related news in the selected window."
            if language == "en"
            else "ไม่พบข่าวเกี่ยวกับน้ำมันในช่วงเวลาที่เลือก"
        )
        return msg

    markdown = _summarize_with_llm(_build_prompt(news, period, language))
    _cache_put(period, language, markdown)
    return markdown
```

- [ ] **Step 6.4: Run, verify pass**

```bash
pytest tests/test_oil_briefing.py -v
```
Expected: 5 passed.

- [ ] **Step 6.5: Commit**

```bash
git add agent/tools/oil_briefing.py tests/test_oil_briefing.py
git commit -m "feat: generate_oil_briefing tool with 6h SQLite cache"
```

---

## Task 7: Wire tools into agent + inject snapshot in system prompt

**Files:**
- Modify: `agent/tools/__init__.py`
- Modify: `agent/main.py`

- [ ] **Step 7.1: Export new tools**

Replace `agent/tools/__init__.py` with:

```python
from agent.tools.oil_briefing import generate_oil_briefing
from agent.tools.oil_context import get_oil_context, oil_snapshot_line
from agent.tools.seafood_prices import (
    get_best_deals,
    get_price_trend,
    query_seafood_prices,
)

ALL_TOOLS = [
    query_seafood_prices,
    get_best_deals,
    get_price_trend,
    get_oil_context,
    generate_oil_briefing,
]
```

- [ ] **Step 7.2: Inject oil snapshot in `agent_node`**

In `agent/main.py`, modify the `agent_node` function. Replace lines 51-70 with:

```python
def agent_node(state: AgentState) -> dict:
    """LLM reasoning node — executes the plan produced by reason_node."""
    from agent.tools import oil_snapshot_line

    llm = get_llm()
    messages = list(state["messages"])

    plan = state.get("current_plan")
    snapshot = oil_snapshot_line()
    system_content = SYSTEM_PROMPT
    if snapshot:
        system_content = SYSTEM_PROMPT + "\n\n" + snapshot
    if plan:
        plan_text = "\n\nExecution plan (follow these steps in order):\n" + "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(plan)
        )
        system_content = system_content + plan_text

    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_content)] + messages
    else:
        messages = [SystemMessage(content=system_content)] + messages[1:]

    response = llm.invoke(messages)
    return {"messages": [response]}
```

- [ ] **Step 7.3: Verify the existing test_reason still passes**

```bash
pytest tests/ -v
```
Expected: all tests pass (existing + new ones from Tasks 1, 2, 4, 5, 6).

- [ ] **Step 7.4: Commit**

```bash
git add agent/tools/__init__.py agent/main.py
git commit -m "feat: register oil tools and inject diesel snapshot into system prompt"
```

---

## Task 8: AI Chat — "Oil Impact Briefing" button + dialog

**Files:**
- Modify: `app/pages/chat.py`

- [ ] **Step 8.1: Read current chat layout**

Open `app/pages/chat.py` and locate where chat input and example prompts are rendered. The dialog and trigger button must sit near the chat input.

- [ ] **Step 8.2: Add the dialog function and button**

Add this near the top of `app/pages/chat.py`, after imports:

```python
from langchain_core.messages import AIMessage, HumanMessage

from agent.tools.oil_briefing import generate_oil_briefing


@st.dialog("Oil Impact Briefing")
def _briefing_dialog(default_lang: str):
    period_label = st.radio("Time range", ["Weekly (last 7 days)", "Monthly (last 30 days)"])
    lang_label = st.radio(
        "Language",
        ["English", "ไทย"],
        index=0 if default_lang == "en" else 1,
    )
    if st.button("Generate"):
        period = "weekly" if "Weekly" in period_label else "monthly"
        language = "en" if lang_label == "English" else "th"
        with st.spinner("Generating briefing…"):
            markdown = generate_oil_briefing.invoke({"period": period, "language": language})
        # Append as an assistant turn so it persists with chat history.
        st.session_state.setdefault("messages", []).append(
            AIMessage(content=f"**Oil Impact Briefing ({period}, {language})**\n\n{markdown}")
        )
        st.rerun()
```

Then, where the chat input/example prompts render, add the trigger button (place adjacent to the existing example-prompts row):

```python
# Detect default language from most recent user message (heuristic)
import re
THAI_RE = re.compile(r"[฀-๿]")


def _default_lang_from_history() -> str:
    msgs = st.session_state.get("messages", [])
    for m in reversed(msgs):
        if isinstance(m, HumanMessage):
            return "th" if THAI_RE.search(str(m.content) or "") else "en"
    return "en"


if st.button("🛢️ Oil Impact Briefing"):
    _briefing_dialog(default_lang=_default_lang_from_history())
```

- [ ] **Step 8.3: Smoke test**

```bash
conda activate MADT
streamlit run app/main.py
```

Open the AI Chat page in the browser. Click the "🛢️ Oil Impact Briefing" button. Verify:
- Dialog opens with two radio groups.
- Language defaults sensibly.
- Clicking Generate posts a markdown response into the chat thread.

If `oil_news.csv` is empty (likely on a fresh checkout), the response should say "No recent oil-related news…" — that's expected. Run `python data/scripts/news_scraper.py` once to seed.

- [ ] **Step 8.4: Commit**

```bash
git add app/pages/chat.py
git commit -m "feat(chat): Oil Impact Briefing modal with period + language selectors"
```

---

## Task 9: Market Insights page (correlation chart + lag table)

**Files:**
- Create: `app/pages/market_insights.py`

- [ ] **Step 9.1: Implement the page**

Create `app/pages/market_insights.py`:

```python
"""Market Insights — oil ↔ seafood correlation explorer."""

from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.loader import load_seafood_data
from data.oil_correlation import MIN_SAMPLE, lag_correlation
from data.oil_loader import diesel_series

LAGS = [0, 7, 14, 21, 28]

st.title("📊 Market Insights — Oil ↔ Seafood")

oil = diesel_series()
seafood_df = load_seafood_data()

if oil.empty:
    st.warning("No oil price data yet. Run `python data/scripts/oil_scraper.py` to seed.")
    st.stop()

if "scrape_date" not in seafood_df.columns or seafood_df["scrape_date"].isna().all():
    st.warning("No historical seafood data yet. Wait for daily scrape to accumulate.")
    st.stop()

species_options = sorted(seafood_df["group_en"].dropna().unique())
species = st.selectbox("Species", species_options)

days = st.slider("Time window (days)", min_value=30, max_value=365, value=90)

# Build seafood daily avg for the selected species
sub = seafood_df.copy()
sub["scrape_date"] = pd.to_datetime(sub["scrape_date"], errors="coerce")
sub = sub[
    (sub["group_en"] == species)
    & sub["price_per_kg"].notna()
    & sub["scrape_date"].notna()
]
if sub.empty:
    st.info(f"No price data available for '{species}'.")
    st.stop()

seafood_series = sub.groupby("scrape_date")["price_per_kg"].mean().sort_index()

# Window
cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
oil_w = oil[oil.index >= cutoff]
seafood_w = seafood_series[seafood_series.index >= cutoff]

# Dual-axis chart
fig = go.Figure()
fig.add_trace(
    go.Scatter(x=seafood_w.index, y=seafood_w.values, name=f"{species} (THB/kg)", yaxis="y1")
)
fig.add_trace(
    go.Scatter(x=oil_w.index, y=oil_w.values, name="Diesel (THB/L)", yaxis="y2")
)
fig.update_layout(
    yaxis=dict(title=f"{species} (THB/kg)"),
    yaxis2=dict(title="Diesel (THB/L)", overlaying="y", side="right"),
    legend=dict(orientation="h"),
    height=420,
)
st.plotly_chart(fig, use_container_width=True)

# Lag correlation
corr = lag_correlation(oil, seafood_series, LAGS)
overlap = pd.concat([oil, seafood_series], axis=1, join="inner").dropna().shape[0]

st.subheader("Lag correlation (Pearson r)")
st.caption(f"Overlap: {overlap} days. Minimum required: {MIN_SAMPLE}.")

if overlap < MIN_SAMPLE:
    st.warning(
        f"Insufficient overlapping data ({overlap} days). "
        f"Need at least {MIN_SAMPLE} days for a meaningful correlation."
    )
else:
    rows = [{"lag (days)": k, "r": v} for k, v in corr.items() if v is not None]
    if rows:
        df = pd.DataFrame(rows).set_index("lag (days)")
        st.dataframe(df.style.format({"r": "{:.3f}"}))
        best_lag, best_r = max(corr.items(), key=lambda kv: (kv[1] or -1))
        st.markdown(
            f"**Takeaway:** {species} prices correlate most strongly with diesel "
            f"~{best_lag} days later (r = {best_r:.2f}, n = {overlap})."
        )

# Limitations
st.subheader("Limitations")
limit_md = (REPO_ROOT / "docs" / "oil-feature-limitations.md")
if limit_md.exists():
    with st.expander("What this view can and can't tell you", expanded=False):
        st.markdown(limit_md.read_text())
```

- [ ] **Step 9.2: Smoke test**

```bash
streamlit run app/main.py
```

Verify:
- Sidebar shows "Market Insights" page.
- Loading the page either renders chart + correlation, or shows the appropriate "insufficient data" / "no data" message.

- [ ] **Step 9.3: Commit**

```bash
git add app/pages/market_insights.py
git commit -m "feat(ui): Market Insights page with dual-axis chart and lag correlation"
```

---

## Task 10: Limitations doc

**Files:**
- Create: `docs/oil-feature-limitations.md`

- [ ] **Step 10.1: Write doc**

Create `docs/oil-feature-limitations.md`:

```markdown
# Oil ↔ Seafood Features — What We Can and Can't Tell You

These notes cover the **Oil Impact Briefing** and the **Market Insights** correlation page.

## What we can show

- **Today's Thai retail diesel price** and recent percent change (7d / 30d), scraped daily from thaioilgroup.com.
- **Recent oil/energy news** that mentions Thai seafood-relevant terms, summarized in Thai or English with source links.
- **Visual overlay** of diesel and seafood prices over the chosen window.
- **Lagged Pearson correlation** between diesel and a chosen species' average price, at lags of 0/7/14/21/28 days.

## What we can't tell you

- **Causation.** A correlation says the two series move together at a given lag. It does not prove that oil *causes* seafood prices to move. Other drivers — weather, fishing season, fuel-subsidy policy changes, festival demand, exchange rates, supply shocks — are not in this model.
- **Forecasts.** We do not predict next week's seafood prices. The features describe what has happened, not what will happen.
- **Statistical significance.** We report `r` but not p-values. With small samples, a flashy `r` may still be noise. Treat any `r` with `n < 90` as suggestive, not confirmatory.

## Sample-size caveat

Lagged correlation needs roughly three months of overlapping daily data before the numbers stabilize. Until then:

- We display `r` only when overlap ≥ 30 days. Below that, the page shows "insufficient data".
- Even at 30–90 days, expect `r` values to swing as new data arrives.

## News-summary caveats

- Briefings are LLM-generated. The model may misinterpret nuance or skip context. **Always click through to the source link before acting on a bullet.**
- Coverage is limited to three RSS feeds (Bangkok Post Business, Reuters Energy, กรุงเทพธุรกิจ). Events those feeds don't cover won't appear.
- Briefings are cached for 6 hours. Breaking news within that window may not show up until the cache expires or a new article is ingested.

## Operational caveats

- The Thaioil scraper depends on a stable HTML structure (`<p class="oil-price">` paired with the preceding `<img alt="...">`). If the site is redesigned, the scraper fails loudly rather than producing garbage.
- The EPPO historical backfill is a manual, one-shot step. If EPPO changes their published file format, the backfill must be re-run by hand.
- All of the above is best-effort student work for MADT 7204, not a commercial-grade data product.
```

- [ ] **Step 10.2: Commit**

```bash
git add docs/oil-feature-limitations.md
git commit -m "docs: oil features limitations"
```

---

## Task 11: EPPO historical backfill (one-shot script)

**Files:**
- Create: `data/scripts/oil_backfill.py`

> **Note:** EPPO does not publish a stable REST endpoint for historical retail prices; they publish dated Excel/CSV files on `eppo.go.th`. URLs change occasionally. This script accepts a path to a downloaded EPPO file rather than fetching it itself, so a broken URL doesn't block the whole pipeline. Document the manual step.

- [ ] **Step 11.1: Implement**

Create `data/scripts/oil_backfill.py`:

```python
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
```

- [ ] **Step 11.2: Commit**

```bash
git add data/scripts/oil_backfill.py
git commit -m "feat: one-shot EPPO historical backfill loader"
```

---

## Task 12: GitHub Actions workflow update

**Files:**
- Modify: `.github/workflows/scrape.yml`

- [ ] **Step 12.1: Add oil + news scraper steps**

Replace the existing `Run scraper` and `Commit and push` steps in `.github/workflows/scrape.yml` with:

```yaml
      - name: Install scraper dependencies
        run: pip install beautifulsoup4 requests pandas feedparser

      - name: Run seafood scraper
        run: python data/scripts/scraper.py

      - name: Run oil scraper
        run: python data/scripts/oil_scraper.py

      - name: Run news scraper
        run: python data/scripts/news_scraper.py

      - name: Commit and push updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/raw/seafood_prices.csv data/raw/oil_prices.csv data/raw/oil_news.csv data/raw/.oil_news_sentinel
          git diff --cached --quiet && echo "No data changes today" || {
            git commit -m "data: daily scrape $(date -u +%Y-%m-%d)"
            git push
          }
```

- [ ] **Step 12.2: Commit**

```bash
git add .github/workflows/scrape.yml
git commit -m "ci: include oil and news scrapers in daily workflow"
```

---

## Task 13: End-to-end manual verification

- [ ] **Step 13.1: Run full test suite**

```bash
conda activate MADT
pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 13.2: Seed local data**

```bash
python data/scripts/oil_scraper.py
python data/scripts/news_scraper.py
```

Verify `data/raw/oil_prices.csv` and `data/raw/oil_news.csv` exist and have rows.

- [ ] **Step 13.3: Run the app**

```bash
streamlit run app/main.py
```

Verify:
- AI Chat page: "Oil Impact Briefing" button opens dialog. Generate posts a briefing to the chat.
- Market Insights page: chart renders (or shows insufficient-data warning if seafood history is too short).
- Limitations panel renders content from `docs/oil-feature-limitations.md`.

- [ ] **Step 13.4: Open a PR**

```bash
git push -u origin feat/oil-impact-briefing
gh pr create --title "feat: Oil Impact Briefing & oil-seafood correlation" --body "$(cat <<'EOF'
## Summary
- Daily scrapers for Thai retail diesel (Thaioil) and oil/energy RSS news from 3 feeds.
- One-shot EPPO historical backfill loader.
- Two new agent tools: `get_oil_context` and `generate_oil_briefing` (6h SQLite cache).
- Diesel snapshot injected into the system prompt so chat responses can flag oil-driven moves.
- AI Chat: "Oil Impact Briefing" modal with weekly/monthly + Thai/English selectors.
- New Market Insights page: dual-axis diesel vs seafood chart + lag correlation table.
- Limitations doc covering correlation ≠ causation, sample-size caveats, news-summary disclaimers.

Spec: `docs/superpowers/specs/2026-05-05-oil-impact-design.md`
Plan: `docs/superpowers/plans/2026-05-05-oil-impact-briefing.md`

## Test plan
- [ ] `pytest tests/` all green
- [ ] `python data/scripts/oil_scraper.py` writes today's row to `oil_prices.csv`
- [ ] `python data/scripts/news_scraper.py` writes filtered articles to `oil_news.csv`
- [ ] AI Chat → Oil Impact Briefing modal opens, Generate posts response
- [ ] Market Insights page renders chart and either correlation table or "insufficient data" message
- [ ] Limitations doc renders inside the page

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
