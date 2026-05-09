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
