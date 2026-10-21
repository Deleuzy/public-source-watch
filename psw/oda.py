"""Client for Folketingets Åbne Data (ODA), https://oda.ft.dk/api/ (OData v3, no key needed).

Polite by default: at most one request per `min_interval` seconds, and every raw
response is written to disk so a re-run inside `max_age` never hits the server.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests

BASE = "https://oda.ft.dk/api/"
PAGE_SIZE = 100  # ODA caps $top at 100
USER_AGENT = "public-source-watch/0.1 (demo; github.com/Deleuzy)"

# Sagstype ids used here (from /api/Sagstype)
TYPE_QUESTION_20 = 10  # § 20-spørgsmål: an MP's question to a minister
TYPE_BILL = 3          # Lovforslag


class OdaClient:
    def __init__(self, cache_dir: Path, min_interval: float = 1.0, max_age: float = 3600,
                 session: requests.Session | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.max_age = max_age
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last = 0.0
        self.stats = {"network": 0, "cache": 0}

    def get(self, entity: str, params: dict, max_age: float | None = None) -> dict:
        params = {"$format": "json", **params}
        url = BASE + entity + "?" + urlencode(params, safe="$,()'")
        path = self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".json")
        max_age = self.max_age if max_age is None else max_age
        if path.exists() and time.time() - path.stat().st_mtime < max_age:
            self.stats["cache"] += 1
            return json.loads(path.read_text())["body"]
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        resp = self.session.get(url, timeout=60)
        self._last = time.monotonic()
        resp.raise_for_status()
        body = resp.json()
        self.stats["network"] += 1
        path.write_text(json.dumps({"url": url, "fetched_at": datetime.now().isoformat(),
                                    "body": body}, ensure_ascii=False))
        return body

    def get_all(self, entity: str, params: dict, **kw) -> list[dict]:
        out, skip = [], 0
        while True:
            page = self.get(entity, {**params, "$top": PAGE_SIZE, "$skip": skip}, **kw)["value"]
            out.extend(page)
            if len(page) < PAGE_SIZE:
                return out
            skip += PAGE_SIZE


def fetch_cases(client: OdaClient, days: int, type_ids=(TYPE_QUESTION_20, TYPE_BILL),
                now: datetime | None = None) -> list[dict]:
    """Cases of the given types updated in the last `days` days, with actors, topics, documents."""
    since = ((now or datetime.now()) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
    types = " or ".join(f"typeid eq {t}" for t in type_ids)
    return client.get_all("Sag", {
        "$filter": f"({types}) and opdateringsdato gt datetime'{since}'",
        "$orderby": "id",
        "$expand": "SagAktør,EmneordSag/Emneord,SagDokument",
    })


def fetch_actors(client: OdaClient, ids, batch: int = 20) -> dict[int, dict]:
    """Actor records by id. Actors change rarely, so they are cached for a week."""
    ids = sorted(set(ids))
    out = {}
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        flt = " or ".join(f"id eq {a}" for a in chunk)
        for a in client.get("Aktør", {"$filter": flt, "$top": batch}, max_age=7 * 86400)["value"]:
            out[a["id"]] = a
    return out


def fetch_lookup(client: OdaClient, entity: str, field: str) -> dict[int, str]:
    """Small code tables such as Sagsstatus, SagAktørRolle, Periode."""
    return {r["id"]: r[field] for r in client.get_all(entity, {}, max_age=7 * 86400)}
