"""Markdown change report and a static HTML view of the connections."""
from __future__ import annotations

import html
from datetime import datetime

from .pipeline import RunResult


def _case_line(c: dict) -> str:
    to = f" → {c['to']['name']}" if c.get("to") else ""
    people = c["askers"] or c["proposers"]
    who = ", ".join(a["name"] for a in people) or (c["ministry"] or {}).get("name") or "–"
    return f"- **{c['number']}** ({c['kind']}, {c['status']}): {c['short_title'] or c['title']}  \n  {'asked by' if c['askers'] else 'proposed by'} {who}{to}"


def render_markdown(r: RunResult) -> str:
    d = r.diff
    lines = [
        f"# Folketinget watch – run {r.run_id}",
        "",
        f"Previous run: {r.prev_run_id if r.prev_run_id is not None else 'none (first run, nothing to compare)'}",
        "",
        "## Numbers",
        "",
        f"- Cases in window: {r.n_cases}",
        f"- Triples extracted: {r.n_triples}",
        f"- Graph: {r.graph.number_of_nodes()} nodes, {r.graph.number_of_edges()} edges",
        f"- Network requests this run: {r.network_requests} (cache hits: {r.cache_hits})",
        "",
        "## Changes since previous run",
        "",
        f"- New cases: {len(d['added'])}",
        f"- Changed cases: {len(d['changed'])}",
        f"- Cases no longer in window: {len(d['removed'])}",
        "",
    ]
    if d["added"]:
        lines += ["### New cases", ""] + [_case_line(c) for c in d["added"]] + [""]
    if d["changed"]:
        lines += ["### Changed cases", ""]
        for ch in d["changed"]:
            c = ch["case"]
            lines.append(f"- **{c['number']}** fields changed: {', '.join(ch['fields'])}")
            for f in ch["fields"]:
                lines.append(f"  - {f}: `{ch['before'][f]}` → `{ch['after'][f]}`")
        lines.append("")
    if not r.prev_run_id:
        lines += ["_No previous snapshot, so every case is listed as new on the first run._", ""]

    lines += ["## Journalist question 1: who asks which minister, by party", "",
              "_UFG is 'Uden for folketingsgrupperne' (MPs outside any party group), so it is a bucket, not one party._",
              ""]
    if r.flows:
        lines += ["| Asking party | Addressee | Questions |", "|---|---|---:|"]
        for (party, to), n in r.flows.most_common(10):
            lines.append(f"| {party} | {to} | {n} |")
    else:
        lines.append("_No questions with a named addressee in this window._")
    lines.append("")

    lines += ["## Journalist question 2: which people connect two topics", ""]
    if r.bridges:
        lines += ["| Topic A | Topic B | People who asked about both |", "|---|---|---|"]
        for b in r.bridges[:10]:
            lines.append(f"| {b['topic_a']} | {b['topic_b']} | {', '.join(b['people'])} |")
    else:
        lines.append("_No person asked about two of the most common topics in this window._")
    lines.append("")

    if r.law_pages:
        lines += ["## Retsinformation pages (rendered with Playwright)", ""]
        for number, rec in sorted(r.law_pages.items()):
            lines.append(f"- Lov nr. {number}: {rec.get('title') or '–'} (Ressort: {rec.get('ressort') or '–'}) – {rec['url']}")
        lines.append("")

    lines += ["---", f"Generated {datetime.now().isoformat(timespec='seconds')} by public-source-watch."]
    return "\n".join(lines) + "\n"


def render_html(r: RunResult) -> str:
    e = html.escape
    rows_flow = "".join(f"<tr><td>{e(p)}</td><td>{e(t)}</td><td>{n}</td></tr>"
                        for (p, t), n in r.flows.most_common(25))
    rows_bridge = "".join(f"<tr><td>{e(b['topic_a'])}</td><td>{e(b['topic_b'])}</td><td>{e(', '.join(b['people']))}</td></tr>"
                          for b in r.bridges[:25])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Folketinget connections – run {r.run_id}</title>
<style>
:root {{ --fg:#1d1d1f; --muted:#6e6e73; --bg:#fff; --line:#d2d2d7; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fg:#f5f5f7; --muted:#a1a1a6; --bg:#1c1c1e; --line:#3a3a3c; }} }}
body {{ font: 15px/1.5 system-ui, sans-serif; color: var(--fg); background: var(--bg); margin: 16px; max-width: 980px; }}
table {{ border-collapse: collapse; width: 100%; margin: 8px 0 24px; }}
th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
p, .muted {{ color: var(--muted); }}
</style></head>
<body>
<h1>Folketinget connections</h1>
<p class="muted">Run {r.run_id}: {r.n_cases} cases, {r.n_triples} triples, {r.graph.number_of_nodes()} nodes.
Static view generated from the graph; no network calls in this page.</p>
<h2>Who asks which minister, by party</h2>
<table><tr><th>Asking party</th><th>Addressee</th><th>Questions</th></tr>{rows_flow}</table>
<h2>People who connect two topics</h2>
<table><tr><th>Topic A</th><th>Topic B</th><th>People</th></tr>{rows_bridge}</table>
</body></html>
"""
