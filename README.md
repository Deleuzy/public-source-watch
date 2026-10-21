# public-source-watch

A small demo of one pattern: **collect → snapshot → detect changes → extract triples → graph → flag**,
run on an open Danish public source that journalists use: Folketinget's open data
(`oda.ft.dk`, parliamentary questions to ministers and bills), plus the rendered law pages on
Retsinformation.

It answers two journalist questions from a graph built with networkx and writes a Markdown change
report per run and a static HTML view of the connections.

No API key, no login, no paid service. Tests run offline on saved fixtures.

## What it does

1. **Collect.** Fetches § 20 questions (`Sagstype` 10) and bills (`Sagstype` 3) updated in the last
   N days from the ODA OData API, with actors, roles, topics and documents expanded. Actor records,
   status and period code tables are fetched too. Every raw response is cached on disk and polite
   rate-limiting is applied between calls.
2. **Playwright step.** For bills that became law, opens `retsinformation.dk/eli/lta/<year>/<number>`
   in headless Chromium and reads the rendered title and "Ressort" (the ministry responsible).
   Retsinformation has no open API, so this is the one place a browser is used. Results are cached.
3. **Snapshot and diff.** Each run is stored in SQLite (`runs`, `case_snapshots`). Each case is
   hashed; the diff against the previous run gives new cases, changed cases (with the fields that
   changed, before and after) and cases that left the window.
4. **Triples.** Rule-based, no LLM. Each rule reads one structured field, so every triple records its
   source (`case:<id>/<field>`). Examples:
   - `person:Emilie Schytte — asked — case:S 40`
   - `person:Emilie Schytte — member_of — party:UFG`
   - `case:S 40 — directed_to — person:Magnus Heunicke`
   - `case:L 23 — concerns_law — law:866`
   - `case:S 40 — has_topic — topic:dagtilbud`
5. **Graph.** A networkx `MultiDiGraph`. Two journalist questions are answered from it:
   - *Who asks which minister, by party?* (party → addressee counts, per question)
   - *Which people connect two topics?* (people who asked about two of the most-used topics)
6. **Output.** `reports/report-runN.md` (change report and both answers), `reports/graph.html`
   (static tables, no network calls) and `reports/summary-runN.json` (counts).

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium   # only needed for the Retsinformation step
.venv/bin/python -m psw run --days 30              # live run; add --no-browser to skip Playwright
.venv/bin/python -m pytest                         # offline tests
```

Useful flags: `--days N` (window), `--min-interval S` (seconds between API calls, default 1),
`--max-age S` (reuse cached API responses younger than S seconds, default 3600), `--no-browser`.
Local state goes to `data/` (git-ignored): the SQLite snapshots and the response cache.

## Real numbers from the run in this repo

Run 1 on 2026-10-21, `--days 30`, live against oda.ft.dk and retsinformation.dk:

| What | Count |
|---|---|
| Cases in window (168 questions, 90 bills) | 258 |
| Questions without a named asker in ODA | 1 |
| Bills that have a numeric law number (Playwright pages read) | 6 |
| Triples extracted | 1,889 |
| Triples by predicate: `has_topic` 488, `member_of` 434, `referred_to` 265, `concerns_ministry` 258, `directed_to` 168, `asked` 167, `proposed` 98, `concerns_law` 10, `co_asked` 1 | |
| Graph nodes (Case 258, Topic 234, Person 68, Committee 24, Ministry 23, Party 13, Law 10) | 630 |
| Graph edges | 1,889 |
| Distinct MPs who asked (in this window) / distinct addressees | 43 / 20 |
| ODA API requests | 14 |

Run 2 (`--max-age 0`, a few minutes later) fetched again: 3 API requests, 258 cases,
**0 new, 0 changed**. Nothing had been updated on the source in between. The change path is
exercised by the tests (see below), not by a live update.

Findings from the run (both are in `reports/report-run1.md`):

1. **Question flow.** The largest flow is from *UFG* (Uden for folketingsgrupperne, MPs outside any
   party group) to *Jakob Engel-Schmidt*: 19 questions. *V* to Engel-Schmidt is next with 7.
   UFG is a bucket of non-aligned MPs, so this is not one party's behaviour. Counts were checked
   against the stored case records.
2. **Bridging people.** Emilie Schytte (UFG) asked 50 questions in the window and is the only person
   who links several topic pairs, e.g. *administration* with *dagtilbud*, *forsvaret*,
   *kollektiv transport* and *strafferet og kriminalitet*. Two other pairs are bridged by two people
   each (politi og våben / strafferet og kriminalitet; retspleje og domstole / udvisning og repatriering).

## Tests

28 tests, all offline (no network, no browser). `tests/fixtures/oda_sample.json` holds three real
ODA records (a question with an addressee, a question with no asker, and bill L 23 that became
law as lov nr. 866), with actor records trimmed to the party shortname.

- `test_normalize.py`: role mapping, empty asker, law number, party parsing
- `test_triples.py`: expected triples and the source field for each
- `test_snapshots.py`: hashing, previous-run lookup, added / changed / removed
- `test_graph.py`: node labels, question flows, topic bridges (also on a synthetic graph)
- `test_oda.py`: cache hit and stale refetch, pagination, date and type filter; a fake session replaces the network
- `test_browser.py`: cached Retsinformation page does not start a browser; parsing the "Ressort" text
- `test_report_and_pipeline.py`: all report sections; an end-to-end second run that reports an
  added case and a changed status

CI (`.github/workflows/ci.yml`) installs `requirements.txt` and runs `pytest` on Python 3.12.

## How it was built

Looked at the sources first with `curl`: the ODA `Sagstype`, `SagAktørRolle`, `Aktørtype`,
`Sagsstatus`, `Periode` tables and an expanded `Sag` query. The Folketinget web pages (`ft.dk`) sit
behind a Cloudflare challenge and return 403 to scripts, so they are not used; Retsinformation
answers normally and is read with Playwright because its law text is rendered by JavaScript.

## Limitations

- **One window only.** It reads the last N days (30 in the run). It is not a full history, and
  nothing is backfilled. The first run is a baseline; "new" means "new since the first run".
- **Change detection is not yet proven on live updates.** Two real runs found no change. The diff
  logic is tested with fixtures only.
- **UFG is a bucket**, not a party; the report says so, but the party flows still mix people.
- **Rule-based only.** No LLM is used, so there are no leftovers to handle. Topics are the
  keywords (`emneord`) that ODA assigns; this code does not classify them.
- **Duplicates are kept.** Two questions with the same title (S 130 and S 131) are two cases.
- **Playwright reads six pages.** Only bills with a numeric law number are looked up, and their
  titles and ministries are reported but not added to the graph.
- **Some law numbers are not numeric** (for example "LTB nr 1", a supplementary budget). They get a
  `Law` node and a `concerns_law` triple, but no Retsinformation lookup.
- **Labels** use the names as ODA stores them; a minister's person record and the ministry office
  are separate actors.
- **Not a verification tool.** A journalist would still read the source document before writing
  anything from these counts.
