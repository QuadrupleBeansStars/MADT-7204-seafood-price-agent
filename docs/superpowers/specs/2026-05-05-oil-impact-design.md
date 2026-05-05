# Oil Impact Briefing & Correlation — Design Spec

**Date:** 2026-05-05
**Status:** Draft, awaiting user review
**Branch:** `feat/oil-impact-briefing`

## 1. Goals

Link the seafood price comparison agent to Thailand's oil/energy context so users can:

1. **Read a concise briefing** of recent oil-related news that may affect seafood costs (Oil Impact Briefing).
2. **See an oil ↔ seafood correlation graph** to understand whether oil moves are showing up in their seafood prices.
3. **Get oil-aware chat responses** — the agent factors current oil conditions into its answers when relevant ("shrimp prices may rise: diesel is up 5% over the last 30 days").

## 2. Non-goals (YAGNI)

- Predictive forecasting of seafood prices. The system is descriptive, not predictive.
- Per-user briefings, alerts, or subscriptions. One global cached briefing per (period, language).
- News sources beyond the initial three. Adding more is a follow-up.
- Sentiment scoring, entity extraction, or any NLP beyond LLM summarization.

## 3. Architecture overview

Three new data pipelines feed two new product surfaces (briefing + correlation graph) and augment the existing agent.

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ thaioilgroup.com│     │ EPPO historical │     │ RSS: BKK Post,   │
│  (daily HTML)   │     │  spreadsheet    │     │ Reuters, กรุงเทพฯ │
└────────┬────────┘     └────────┬────────┘     └─────────┬────────┘
         │ daily                  │ one-shot              │ daily
         ▼                        ▼                       ▼
   oil_scraper.py           oil_backfill.py        news_scraper.py
         │                        │                       │
         └────────┬───────────────┘                       │
                  ▼                                       ▼
         data/raw/oil_prices.csv               data/raw/oil_news.csv
                  │                                       │
                  └────────────────┬──────────────────────┘
                                   ▼
        ┌──────────────────────────────────────────────┐
        │  Agent tools                                  │
        │  - get_oil_context(species)                   │
        │  - generate_oil_briefing(period, language)    │
        │                                               │
        │  System prompt: 1-line oil snapshot           │
        └──────────────────────────────────────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
         AI Chat page                    Market Insights page
         - Briefing button                - Dual-axis chart
           → st.dialog                    - Lag correlation table
           → posts to chat                - Limitations section
```

## 4. Data pipelines

### 4.1 `data/scripts/oil_scraper.py` (daily)

- Fetches `https://www.thaioilgroup.com/en/oil-prices-information/`.
- Parses `<p class="oil-price">` elements. Each price is paired with the immediately preceding `<img alt="...">` to identify the product (Diesel, Diesel B20, Gasohol 95, etc.).
- Appends one row per product per day to `data/raw/oil_prices.csv` with columns: `date, product, thb_per_litre, source`.
- Idempotent: if today's date already has rows for this source, skip.
- On parse failure (HTML structure changed), log loudly and exit non-zero — no silent failure.

### 4.2 `data/scripts/oil_backfill.py` (one-shot)

- Downloads EPPO's historical retail price file (URL pinned in script with comment for manual update if EPPO restructures).
- Normalizes into the same `oil_prices.csv` schema with `source = "eppo"`.
- Run manually at setup time. Not part of the daily scheduler.

### 4.3 `data/scripts/news_scraper.py` (daily)

- Pulls RSS feeds from three sources:
  - Bangkok Post Business
  - Reuters Energy
  - กรุงเทพธุรกิจ (or ฐานเศรษฐกิจ if กรุงเทพธุรกิจ's RSS is unstable)
- Filters items by keyword relevance (oil, diesel, fuel, energy, น้ำมัน, ดีเซล, พลังงาน, subsidy, fishing, seafood, supply chain, logistics).
- Appends to `data/raw/oil_news.csv`: `date, source, title, url, snippet, language`.
- Deduplicates by URL.

### 4.4 Scheduler

The existing daily seafood-price cron also triggers `oil_scraper.py` and `news_scraper.py`. Cache invalidation (see §6) hooks into successful news ingestion.

## 5. Agent changes

### 5.1 New tool: `get_oil_context(species: str | None) -> dict`

Returns:

```python
{
  "diesel_thb_per_l": 33.80,
  "change_7d_pct": 2.1,
  "change_30d_pct": 5.4,
  "lag_correlation": {  # only when species is provided and n >= 30
    "0": 0.12, "7": 0.31, "14": 0.51, "21": 0.44, "28": 0.28
  } | None,
  "n_days_overlap": 87
}
```

When the species lacks ≥30 days of overlapping data, `lag_correlation` is `None` and the agent is instructed (via tool description) to say so explicitly.

### 5.2 New tool: `generate_oil_briefing(period: "weekly"|"monthly", language: "th"|"en") -> str`

- Checks cache (see §6). On hit, returns cached markdown.
- On miss: pulls news from `oil_news.csv` within the period window, builds a prompt with title + url + snippet for each article, asks Claude to produce ≤5 bullet points in the requested language with inline source links and a short "possible seafood cost impact" line per bullet.
- Writes result to cache. Returns markdown.
- Returns markdown including a final "Practical actions" section per the feature spec.

### 5.3 System prompt augmentation

Inject a one-line snapshot at request build time:

```
Current oil context: Diesel 33.80 THB/L (+2.1% 7d, +5.4% 30d).
```

This gives the agent a trigger to call `get_oil_context` with a species when oil-related concerns are relevant. Without the snapshot, the agent has no reason to investigate oil unprompted.

## 6. Caching

### 6.1 Briefing cache

- Storage: small SQLite table `briefing_cache(period, language, generated_at, markdown)` or equivalent JSON file. SQLite preferred for atomicity.
- Key: `(period, language)`. Four entries max.
- TTL: 6 hours.
- Invalidation: `news_scraper.py` writes a sentinel after successful ingestion; cache lookup checks sentinel timestamp and treats entries older than the sentinel as stale even within TTL.

### 6.2 Oil context

Not cached. `get_oil_context` reads `oil_prices.csv` directly each call — it's a sub-millisecond pandas operation.

## 7. UI changes

### 7.1 AI Chat page (`app/pages/`)

- New button **"Oil Impact Briefing"** placed near the chat input.
- Click opens `st.dialog` with:
  - Radio: Weekly (last 7 days) / Monthly (last 30 days)
  - Radio: ไทย / English (default = current chat language)
  - "Generate" button
- On Generate: call `generate_oil_briefing`, append the returned markdown to chat history as an assistant message, close dialog.

### 7.2 New page: Market Insights (`app/pages/market_insights.py`)

Components, top to bottom:

1. **Species selector** (dropdown, populated from seafood data).
2. **Time-range slider** (default last 90 days).
3. **Dual-axis line chart**: left axis = avg seafood THB/kg for selected species; right axis = diesel THB/L. Plotly or Altair.
4. **Lag correlation table**: lags 0, 7, 14, 21, 28 days. Pearson r. Highlight strongest.
5. **One-line takeaway**: e.g. *"Shrimp prices correlate most with diesel ~14 days later (r = 0.51, n = 87)."* When `n < 30`, replace with *"Insufficient overlapping data — need at least 30 days."*
6. **Limitations panel** (always visible, collapsible): renders `docs/oil-feature-limitations.md`.

## 8. Limitations doc (`docs/oil-feature-limitations.md`)

Spelled out for users and graders:

- Correlation ≠ causation. Seafood prices respond to weather, season, fuel-subsidy policy, festival demand, and many other factors not modeled here.
- Sample-size caveat: lagged correlation needs ~3 months of overlapping daily data. Before then, displayed correlation values may be noisy or unavailable; the system shows "insufficient data" when `n < 30`.
- LLM summaries can misrepresent sources. Every bullet links to its original article so users can verify.
- The Thaioil scraper depends on a stable HTML structure (`<p class="oil-price">`). A site redesign breaks the daily price feed and the system will surface a loud error rather than fail silently.
- The EPPO backfill is a one-shot, manual step. If EPPO changes their file format, the backfill must be re-run by hand.
- News coverage is limited to three feeds. Events that the chosen sources don't cover won't appear in the briefing.

## 9. Testing

- Unit tests for HTML parsing (`oil_scraper.py`) using a saved fixture of the live page.
- Unit tests for RSS filtering keyword matching.
- Unit test for lag correlation function with a synthetic dataset where the correct lag is known.
- Integration test: stub LLM call, ensure `generate_oil_briefing` returns markdown with at least one source link.
- Manual smoke test: run the dev server, click the briefing button, view Market Insights page with real data after backfill.

## 10. Open questions / follow-ups

- If three RSS feeds prove insufficient for monthly briefings (too few articles), add EPPO press release scraping or a fourth source.
- If users want PDF/email export of briefings, that's a follow-up.
- Forecasting (predict next-week seafood price from oil) is explicitly out of scope but a natural next project.
