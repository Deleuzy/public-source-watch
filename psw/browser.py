"""Playwright step: read the rendered Retsinformation page for an enacted law.

Retsinformation has no open API, and its law text is rendered by JavaScript, so
this is the one place a browser is used. It only runs for cases that have a law
number (a bill that has become law) and results are cached on disk, so a second
run does not open a browser again.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

URL = "https://www.retsinformation.dk/eli/lta/{year}/{number}"
TITLE_SELECTOR = ".Titel2"
MIN_INTERVAL = 3.0  # seconds between page loads


def _parse_ressort(text: str) -> str | None:
    """The line after the 'Ressort' heading on the rendered page."""
    m = re.search(r"Ressort\n([^\n]+)", text)
    return m.group(1).strip() if m else None


def fetch_law_pages(laws: list[tuple[str, int]], cache_dir: Path, sync_playwright=None) -> dict[str, dict]:
    """laws: list of (law_number, year). Returns {law_number: {"title", "ressort", "url"}}."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict] = {}
    todo = []
    for number, year in laws:
        cache = cache_dir / f"lta-{year}-{number}.json"
        if cache.exists():
            result[number] = json.loads(cache.read_text())
        else:
            todo.append((number, year, cache))
    if not todo:
        return result

    if sync_playwright is None:
        from playwright.sync_api import sync_playwright  # imported lazily so tests need no browser

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent="public-source-watch/0.1 (demo)")
        try:
            for i, (number, year, cache) in enumerate(todo):
                if i:
                    time.sleep(MIN_INTERVAL)
                url = URL.format(year=year, number=number)
                page.goto(url, wait_until="networkidle", timeout=60000)
                title = None
                if page.locator(TITLE_SELECTOR).count():
                    title = page.locator(TITLE_SELECTOR).first.inner_text().strip()
                record = {"title": title, "ressort": _parse_ressort(page.inner_text("body")), "url": url}
                cache.write_text(json.dumps(record, ensure_ascii=False))
                result[number] = record
        finally:
            browser.close()
    return result
