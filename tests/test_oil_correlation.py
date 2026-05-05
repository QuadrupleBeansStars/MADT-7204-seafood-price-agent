import math
import pandas as pd
from data.oil_correlation import lag_correlation, pct_change, MIN_SAMPLE

# Seed for reproducible randomness
import numpy as np
np.random.seed(42)


def _series(values, start="2026-01-01"):
    idx = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(values, index=idx)


def test_lag_correlation_perfect_lag_14():
    """Seafood lags oil by exactly 14 days → r at lag 14 should be ~1.0."""
    # Create oil series with random walk pattern
    oil_vals = np.cumsum(np.random.randn(60))
    oil = _series(oil_vals)
    # Seafood follows oil with a 14-day lag: seafood[t] = oil[t-14]
    # Pad first 14 days with NaN, then copy oil's values from offset
    seafood_vals = [float('nan')] * 14 + list(oil_vals[:46])
    seafood = _series(seafood_vals)
    result = lag_correlation(oil, seafood, lags=[0, 7, 14, 21])
    # At lag=14, shifting seafood back by 14 days aligns it perfectly with oil
    assert result[14] is not None and result[14] > 0.99
    # At lag=0, correlation should be much lower than at lag=14 due to misalignment
    assert result[0] is not None and result[0] < result[14]


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
