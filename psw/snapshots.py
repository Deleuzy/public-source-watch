"""SQLite snapshot store and change detection.

Each run is stored as one row in `runs` and one row per case in `case_snapshots`
(the normalized case as JSON plus a hash of it). Diffing two runs compares the
hashes, so a change in any field a journalist cares about shows up.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    source TEXT NOT NULL,
    days INTEGER NOT NULL,
    n_cases INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS case_snapshots (
    run_id INTEGER NOT NULL REFERENCES runs(id),
    case_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    body TEXT NOT NULL,
    PRIMARY KEY (run_id, case_id)
);
"""


def content_hash(case: dict) -> str:
    return hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


class SnapshotStore:
    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def save_run(self, cases: list[dict], source: str, days: int, started_at: datetime | None = None) -> int:
        cur = self.db.execute(
            "INSERT INTO runs (started_at, source, days, n_cases) VALUES (?, ?, ?, ?)",
            ((started_at or datetime.now()).isoformat(timespec="seconds"), source, days, len(cases)))
        run_id = cur.lastrowid
        self.db.executemany(
            "INSERT INTO case_snapshots (run_id, case_id, content_hash, body) VALUES (?, ?, ?, ?)",
            [(run_id, c["id"], content_hash(c), json.dumps(c, ensure_ascii=False)) for c in cases])
        self.db.commit()
        return run_id

    def previous_run_id(self, before_run_id: int | None = None) -> int | None:
        row = self.db.execute(
            "SELECT id FROM runs WHERE id < ? ORDER BY id DESC LIMIT 1",
            (before_run_id if before_run_id is not None else 10**12,)).fetchone()
        return row["id"] if row else None

    def cases_of(self, run_id: int) -> dict[int, dict]:
        rows = self.db.execute("SELECT case_id, body FROM case_snapshots WHERE run_id = ?", (run_id,))
        return {r["case_id"]: json.loads(r["body"]) for r in rows}

    def close(self):
        self.db.close()


def diff_cases(old: dict[int, dict], new: dict[int, dict]) -> dict:
    """Compare two snapshots. Returns new cases, and changed cases with the fields that differ."""
    added = [new[k] for k in sorted(new.keys() - old.keys())]
    removed = [old[k] for k in sorted(old.keys() - new.keys())]
    changed = []
    for k in sorted(new.keys() & old.keys()):
        if content_hash(old[k]) == content_hash(new[k]):
            continue
        fields = sorted(f for f in set(old[k]) | set(new[k]) if old[k].get(f) != new[k].get(f))
        changed.append({"case": new[k], "fields": fields,
                        "before": {f: old[k].get(f) for f in fields},
                        "after": {f: new[k].get(f) for f in fields}})
    return {"added": added, "removed": removed, "changed": changed}
