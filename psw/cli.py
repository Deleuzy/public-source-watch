"""Command line: `python -m psw run --days 30`."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import browser, oda, pipeline
from .report import render_html
from .snapshots import SnapshotStore

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="psw", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="collect, snapshot, diff, build graph, write reports")
    run.add_argument("--days", type=int, default=30, help="look back this many days (default 30)")
    run.add_argument("--db", type=Path, default=ROOT / "data" / "snapshots.sqlite")
    run.add_argument("--cache", type=Path, default=ROOT / "data" / "cache")
    run.add_argument("--out", type=Path, default=ROOT / "reports")
    run.add_argument("--no-browser", action="store_true", help="skip the Playwright step")
    run.add_argument("--min-interval", type=float, default=1.0, help="seconds between API calls")
    run.add_argument("--max-age", type=float, default=3600, help="reuse cached API responses younger than this (seconds)")
    args = ap.parse_args(argv)

    started = datetime.now()
    client = oda.OdaClient(args.cache, min_interval=args.min_interval, max_age=args.max_age)
    cases = pipeline.collect(client, args.days, now=started)
    law_pages = {}
    if not args.no_browser:
        laws = sorted({(c["law_number"], int(c["law_date"][:4])) for c in cases
                       if c["law_number"] and c["law_number"].isdigit() and c["law_date"]})
        if laws:
            law_pages = browser.fetch_law_pages(laws, args.cache / "retsinformation")
    store = SnapshotStore(args.db)
    result = pipeline.run(cases, store, days=args.days, network_requests=client.stats["network"],
                          cache_hits=client.stats["cache"], law_pages=law_pages, started_at=started)
    store.close()
    paths = pipeline.write_outputs(result, args.out, render_html)
    for name, p in paths.items():
        print(f"{name}: {p}")
    print(f"run {result.run_id}: {result.n_cases} cases, {result.n_triples} triples, "
          f"new {len(result.diff['added'])}, changed {len(result.diff['changed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
