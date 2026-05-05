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
