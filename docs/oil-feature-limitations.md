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
