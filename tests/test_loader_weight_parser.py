"""Tests for the option-text weight parser in data/loader.

The parser converts shops' free-text option strings ("500 กรัม",
"1.1 กิโลกรัม", "L: 7-10 ตัวโล") into a numeric weight_kg, so the
existing per-kg calculation can run on items the source CSV otherwise
shows as 'pack-only'. Without this, ปลาทู ฿99/pack at 200g looked
'cheaper' than the ฿115/kg market benchmark — a unit-mixed comparison
the agent then surfaced as a recommendation.
"""
from __future__ import annotations

import pandas as pd
import pytest

from data.loader import (
    _compute_per_kg_from_weight,
    _fill_weight_from_option,
    _parse_weight_kg_from_option,
)


# Each (option_text, expected_kg or None) pair captures one shape of
# option string we observed in production data.
@pytest.mark.parametrize("option,expected", [
    # Explicit grams — user's stated example shape
    ("500 กรัม", 0.5),
    ("280g", 0.28),
    ("500กรัม", 0.5),
    # Explicit kilograms
    ("1.1 กิโลกรัม", 1.1),
    ("1.3กิโล", 1.3),
    ("1 กก", 1.0),
    ("1.5kg", 1.5),
    # Per-kg markers — "ตัวโล" means "pieces per kilo", "(กก)" is a
    # parenthetical kg-unit suffix; both signal the price IS per-kg
    ("L: 7-10 ตัวโล", 1.0),
    ("8-12 ตัว (กก)", 1.0),
    ("8-12 ตัว (kg)", 1.0),
    # Mixed: gram unit must win over the implicit per-kg signal
    ("26-35 ตัว (280กรัม)", 0.28),
    # No weight signal — pure piece counts stay None ('pack' territory)
    ("3 ชิ้น/แพ็ค", None),
    ("26-35 ตัว", None),
    ("-", None),
    ("", None),
])
def test_parse_weight_kg_from_option(option, expected):
    assert _parse_weight_kg_from_option(option) == expected


def test_fill_weight_from_option_only_fills_missing():
    """Existing non-null weight_kg must NOT be overwritten — the source
    CSV is authoritative when it provides a value. We only backfill NaN."""
    df = pd.DataFrame({
        "option": ["500 กรัม", "1 กก", "ignored"],
        "weight_kg": [None, None, 9.99],  # third row pre-populated
    })
    out = _fill_weight_from_option(df.copy())
    assert out.loc[0, "weight_kg"] == 0.5
    assert out.loc[1, "weight_kg"] == 1.0
    assert out.loc[2, "weight_kg"] == 9.99  # untouched


def test_compute_per_kg_normalises_pack_to_per_kg():
    """End-to-end: 500g pack at ฿1500 must become ฿3000/kg after both
    helpers run. This is the user's headline normalisation request."""
    df = pd.DataFrame({
        "option": ["ปูม้า 500 กรัม", "3 ชิ้น/แพ็ค"],
        "weight_kg": [None, None],
        "selling_price": [1500.0, 250.0],
        "price_per_kg": [None, None],
    })
    df = _fill_weight_from_option(df)
    df = _compute_per_kg_from_weight(df)
    assert df.loc[0, "weight_kg"] == 0.5
    assert df.loc[0, "price_per_kg"] == 3000.0
    # Pure-piece pack stays as pack — no spurious per-kg estimate.
    assert pd.isna(df.loc[1, "weight_kg"])
    assert pd.isna(df.loc[1, "price_per_kg"])


def test_helpers_do_not_mutate_input():
    """Regression: both helpers must return a NEW DataFrame and leave the
    caller's reference untouched. Mutating shared dfs broke the contract
    in early drafts (assignments to df['weight_kg']/df['price_per_kg']
    leaked back into the caller's view of the data)."""
    original = pd.DataFrame({
        "option": ["500 กรัม", "3 ชิ้น/แพ็ค"],
        "weight_kg": [None, None],
        "selling_price": [1500.0, 250.0],
        "price_per_kg": [None, None],
    })
    snapshot = original.copy()

    out_a = _fill_weight_from_option(original)
    out_b = _compute_per_kg_from_weight(out_a)

    # Returned DataFrames carry the new values…
    assert out_a.loc[0, "weight_kg"] == 0.5
    assert out_b.loc[0, "price_per_kg"] == 3000.0
    # …but the original input is untouched.
    pd.testing.assert_frame_equal(original, snapshot)
