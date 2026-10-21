import json

from psw import browser


def test_cached_law_page_does_not_open_a_browser(tmp_path):
    cache = tmp_path / "lta-2026-866.json"
    record = {"title": "Lov om ændring", "ressort": "Klima-, Energi- og Forsyningsministeriet", "url": "x"}
    cache.write_text(json.dumps(record))

    def must_not_launch(*a, **kw):
        raise AssertionError("browser should not start when the page is cached")

    got = browser.fetch_law_pages([("866", 2026)], tmp_path, sync_playwright=must_not_launch)
    assert got == {"866": record}


def test_ressort_is_read_from_rendered_text():
    text = "Gældende\nRessort\nKlima-, Energi- og Forsyningsministeriet\nYderligere oplysninger"
    assert browser._parse_ressort(text) == "Klima-, Energi- og Forsyningsministeriet"
    assert browser._parse_ressort("ingen") is None
