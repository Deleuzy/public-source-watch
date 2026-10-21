"""`python -m psw.classify`: place the latest saved run's cases in the org tree."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .classifier import Classifier
from .report import write

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="psw.classify", description=__doc__)
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "snapshots.sqlite")
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "classifications")
    ap.add_argument("--out", type=Path, default=ROOT / "reports")
    args = ap.parse_args(argv)

    db = sqlite3.connect(args.db)
    (run_id,) = db.execute("select max(id) from runs").fetchone()
    cases = [json.loads(b) for (b,) in db.execute(
        "select body from case_snapshots where run_id = ? order by case_id", (run_id,))]
    db.close()

    s = write(run_id, cases, Classifier(), args.data, args.out)
    print(f"run {run_id}: {s['cases']} cases, outside the two ministries {s['unclassified_ministry']}, "
          f"no area {s['unclassified_area']}")
    print(f"report: {args.out / f'classification-run{run_id}.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
