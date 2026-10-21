import json
from datetime import datetime
from urllib.parse import unquote_plus

import pytest

from psw import oda


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


class FakeSession:
    """Stands in for requests.Session: counts calls, never touches the network."""

    def __init__(self, pages):
        self.pages = pages  # list of response bodies, served in order
        self.calls = []
        self.headers = {}

    def get(self, url, timeout=None):
        self.calls.append(url)
        return FakeResponse(self.pages[len(self.calls) - 1])


def test_second_call_is_served_from_cache(tmp_path):
    session = FakeSession([{"value": [{"id": 1}]}])
    client = oda.OdaClient(tmp_path, min_interval=0, session=session)
    first = client.get("Sag", {"$top": 1})
    second = client.get("Sag", {"$top": 1})
    assert first == second == {"value": [{"id": 1}]}
    assert len(session.calls) == 1
    assert client.stats == {"network": 1, "cache": 1}


def test_stale_cache_is_refetched(tmp_path):
    session = FakeSession([{"value": [{"id": 1}]}, {"value": [{"id": 2}]}])
    client = oda.OdaClient(tmp_path, min_interval=0, max_age=0, session=session)
    client.get("Sag", {})
    assert client.get("Sag", {})["value"] == [{"id": 2}]
    assert len(session.calls) == 2


def test_pagination_stops_on_short_page(tmp_path):
    full = {"value": [{"id": i} for i in range(oda.PAGE_SIZE)]}
    last = {"value": [{"id": 999}]}
    session = FakeSession([full, last])
    client = oda.OdaClient(tmp_path, min_interval=0, session=session)
    rows = client.get_all("Sag", {})
    assert len(rows) == oda.PAGE_SIZE + 1
    assert len(session.calls) == 2


def test_fetch_cases_filters_by_type_and_date(tmp_path):
    session = FakeSession([{"value": []}])
    client = oda.OdaClient(tmp_path, min_interval=0, session=session)
    oda.fetch_cases(client, days=7, now=datetime(2026, 10, 21))
    url = unquote_plus(session.calls[0])
    assert "typeid eq 10" in url and "typeid eq 3" in url
    assert "2026-10-14" in url


def test_cache_file_is_plain_json(tmp_path):
    session = FakeSession([{"value": []}])
    client = oda.OdaClient(tmp_path, min_interval=0, session=session)
    client.get("Sag", {})
    stored = [json.loads(p.read_text()) for p in tmp_path.glob("*.json")]
    assert stored[0]["body"] == {"value": []}
    assert "fetched_at" in stored[0]
