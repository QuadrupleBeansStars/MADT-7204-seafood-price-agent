import pandas as pd
import pytest

from agent.tools import talaadthai_benchmark as mod
from agent.tools.talaadthai_benchmark import get_talaadthai_benchmark


@pytest.fixture
def fake_benchmark(monkeypatch):
    df = pd.DataFrame([
        {
            "group_en": "Vannamei Shrimp",
            "group_th": "กุ้งขาว",
            "price_per_kg": 245.0,
            "price_min": 180.0,
            "price_max": 315.0,
            "n_variants": 3,
            "snapshot_date": pd.Timestamp("2026-03-24"),
            "link": "https://talaadthai.com/products/white-shrimp",
        },
        {
            "group_en": "Salmon",
            "group_th": "ปลาแซลมอน",
            "price_per_kg": 575.0,
            "price_min": 400.0,
            "price_max": 750.0,
            "n_variants": 5,
            "snapshot_date": pd.Timestamp("2025-12-01"),
            "link": "https://talaadthai.com/products/salmon",
        },
    ])
    monkeypatch.setattr(mod, "load_talaadthai_benchmark", lambda: df)
    return df


def test_returns_benchmark_for_english_match(fake_benchmark):
    out = get_talaadthai_benchmark.invoke({"species": "Vannamei Shrimp"})
    assert out["found"] is True
    assert out["group_en"] == "Vannamei Shrimp"
    assert out["price_per_kg"] == 245.0
    assert out["snapshot_date"] == "2026-03-24"
    assert out["link"].startswith("https://talaadthai.com/")


def test_returns_benchmark_for_thai_match(fake_benchmark):
    out = get_talaadthai_benchmark.invoke({"species": "กุ้งขาว"})
    assert out["found"] is True
    assert out["group_en"] == "Vannamei Shrimp"


def test_partial_substring_match_works(fake_benchmark):
    out = get_talaadthai_benchmark.invoke({"species": "salmon"})
    assert out["found"] is True
    assert out["group_th"] == "ปลาแซลมอน"


def test_unknown_species_returns_found_false(fake_benchmark):
    out = get_talaadthai_benchmark.invoke({"species": "platypus"})
    assert out == {"found": False, "species": "platypus"}


def test_empty_benchmark_returns_found_false(monkeypatch):
    monkeypatch.setattr(mod, "load_talaadthai_benchmark", lambda: pd.DataFrame())
    out = get_talaadthai_benchmark.invoke({"species": "Vannamei Shrimp"})
    assert out["found"] is False
