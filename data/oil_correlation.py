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
