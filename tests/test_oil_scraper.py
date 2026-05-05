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
