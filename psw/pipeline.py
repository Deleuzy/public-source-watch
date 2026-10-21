"""One run end to end: collect -> snapshot -> diff -> triples -> graph -> reports."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import networkx as nx

from . import graph as graph_mod
from . import oda
from .normalize import actor_ids, normalize_case
from .snapshots import SnapshotStore, diff_cases
from .triples import Triple, extract


@dataclass
class RunResult:
    run_id: int
    prev_run_id: int | None
    n_cases: int
    n_triples: int
    diff: dict
    flows: Counter
    bridges: list[dict]
    graph: nx.MultiDiGraph
    network_requests: int
    cache_hits: int
    law_pages: dict = field(default_factory=dict)


def collect(client: oda.OdaClient, days: int, now: datetime | None = None) -> list[dict]:
    raw = oda.fetch_cases(client, days, now=now)
    actors = oda.fetch_actors(client, actor_ids(raw))
    statuses = oda.fetch_lookup(client, "Sagsstatus", "status")
    periods = oda.fetch_lookup(client, "Periode", "kode")
    return [normalize_case(c, actors, statuses, periods) for c in raw]


def labels_for(cases: list[dict]) -> dict[str, str]:
    """Human-readable labels for graph nodes, taken from the case records."""
    from .triples import case_node, committee_node, party_node, person_node, ministry_node, law_node, topic_node
    labels: dict[str, str] = {}
    for c in cases:
        labels[case_node(c)] = f"{c['number']}: {c['short_title'] or c['title'] or ''}"[:90]
        for p in c["askers"] + c["co_askers"] + c["proposers"]:
            labels[person_node(p)] = p["name"]
            if p.get("party"):
                labels[party_node(p["party"])] = p["party"]
        for key in ("to", "answered_by"):
            if c[key]:
                labels[person_node(c[key])] = c[key]["name"]
        if c["ministry"]:
            labels[ministry_node(c["ministry"])] = c["ministry"]["name"]
        if c["law_number"]:
            labels[law_node(c["law_number"])] = f"Lov nr. {c['law_number']}"
        for t in c["topics"]:
            labels[topic_node(t)] = t
        for name in c["committees"]:
            labels[committee_node(name)] = name
    return labels


def run(cases: list[dict], store: SnapshotStore, days: int, source: str = "oda.ft.dk",
        network_requests: int = 0, cache_hits: int = 0, law_pages: dict | None = None,
        started_at: datetime | None = None) -> RunResult:
    prev_id = store.previous_run_id()
    old = store.cases_of(prev_id) if prev_id is not None else {}
    run_id = store.save_run(cases, source=source, days=days, started_at=started_at)
    diff = diff_cases(old, {c["id"]: c for c in cases})

    triples: list[Triple] = [t for c in cases for t in extract(c)]
    g = graph_mod.build_graph(triples, labels_for(cases))
    return RunResult(
        run_id=run_id, prev_run_id=prev_id, n_cases=len(cases), n_triples=len(triples),
        diff=diff, flows=graph_mod.question_flows(g), bridges=graph_mod.topic_bridges(g),
        graph=g, network_requests=network_requests, cache_hits=cache_hits,
        law_pages=law_pages or {})


def write_outputs(result: RunResult, out_dir: Path, render_html) -> dict[str, Path]:
    from .report import render_markdown
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f"report-run{result.run_id}.md"
    md.write_text(render_markdown(result))
    html = out_dir / "graph.html"
    html.write_text(render_html(result))
    summary = out_dir / f"summary-run{result.run_id}.json"
    summary.write_text(json.dumps({
        "run_id": result.run_id, "previous_run_id": result.prev_run_id,
        "cases": result.n_cases, "triples": result.n_triples,
        "nodes": result.graph.number_of_nodes(), "edges": result.graph.number_of_edges(),
        "added": len(result.diff["added"]), "changed": len(result.diff["changed"]),
        "removed": len(result.diff["removed"]),
        "network_requests": result.network_requests, "cache_hits": result.cache_hits,
    }, indent=2, ensure_ascii=False))
    return {"markdown": md, "html": html, "summary": summary}
