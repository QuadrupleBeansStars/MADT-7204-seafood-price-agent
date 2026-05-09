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
