"""Classify one run's cases and write the placements plus a count report."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .classifier import UNCLASSIFIED, Classifier, Placement


def summarise(placements: list[Placement]) -> dict:
    return {
        "cases": len(placements),
        "by_ministry": Counter(p.ministry for p in placements),
        "by_area": Counter(p.area for p in placements if p.ministry != UNCLASSIFIED),
        "by_rule": Counter(r for p in placements for r in (p.ministry_rule, p.area_rule) if r),
        "unclassified_ministry": sum(p.ministry == UNCLASSIFIED for p in placements),
        "unclassified_area": sum(p.ministry != UNCLASSIFIED and p.area == UNCLASSIFIED for p in placements),
    }


def render_markdown(run_id: int, summary: dict, names: dict[str, str], cases: dict[int, dict],
                    placements: list[Placement]) -> str:
    lines = [f"# Classification – run {run_id}", "",
             f"Cases: {summary['cases']}", "",
             "## Per ministry", "", "| Ministry | Cases |", "|---|---:|"]
    for node, n in summary["by_ministry"].most_common():
        lines.append(f"| {names[node]} | {n} |")
    lines += ["", "## Per area (inside the two ministries)", "", "| Area | Cases |", "|---|---:|"]
    for node, n in summary["by_area"].most_common():
        lines.append(f"| {names[node]} | {n} |")
    lines += ["", "## Unclassified", "",
              f"- No ministry rule matched (outside the two ministries in org.yaml): {summary['unclassified_ministry']}",
              f"- Ministry matched but no area rule matched: {summary['unclassified_area']}", ""]
    open_cases = [p for p in placements if p.ministry != UNCLASSIFIED and p.area == UNCLASSIFIED]
    if open_cases:
        lines += ["| Case | Title | ODA keywords |", "|---|---|---|"]
        for p in open_cases:
            c = cases[p.case_id]
            lines.append(f"| {c['number']} | {(c['title'] or '')[:80]} | {', '.join(c['topics'])} |")
    lines += ["", "## Rules used", "", "| Rule | Times |", "|---|---:|"]
    for rule, n in sorted(summary["by_rule"].items()):
        lines.append(f"| {rule} | {n} |")
    return "\n".join(lines) + "\n"


def write(run_id: int, cases: list[dict], classifier: Classifier, data_dir: Path, report_dir: Path) -> dict:
    placements = [classifier.classify(c) for c in cases]
    summary = summarise(placements)
    data_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / f"run-{run_id}.jsonl", "w") as f:
        for p in placements:
            f.write(json.dumps(p.__dict__, ensure_ascii=False) + "\n")
    md = render_markdown(run_id, summary, classifier.names(), {c["id"]: c for c in cases}, placements)
    (report_dir / f"classification-run{run_id}.md").write_text(md)
    return summary
