from datetime import datetime

from psw.pipeline import run, write_outputs
from psw.report import render_html, render_markdown
from psw.snapshots import SnapshotStore


def test_markdown_has_all_sections(tmp_path, normalized):
    store = SnapshotStore(tmp_path / "s.sqlite")
    result = run(normalized, store, days=30)
    md = render_markdown(result)
    for heading in ["## Numbers", "## Changes since previous run", "### New cases",
                    "## Journalist question 1", "## Journalist question 2"]:
        assert heading in md
    assert "Triples extracted: %d" % result.n_triples in md
    store.close()


def test_second_run_reports_change_end_to_end(tmp_path, normalized, changed_copy):
    store = SnapshotStore(tmp_path / "s.sqlite")
    run(normalized, store, days=30, started_at=datetime(2026, 10, 21, 9))
    second = run(changed_copy, store, days=30, started_at=datetime(2026, 10, 21, 10))
    md = render_markdown(second)
    assert "New cases: 1" in md
    assert "Changed cases: 1" in md
    assert "status:" in md and "Besvaret, endeligt-test" in md
    store.close()


def test_outputs_are_written(tmp_path, normalized):
    store = SnapshotStore(tmp_path / "s.sqlite")
    result = run(normalized, store, days=30)
    paths = write_outputs(result, tmp_path / "out", render_html)
    assert paths["markdown"].exists() and paths["html"].exists() and paths["summary"].exists()
    assert "<table>" in paths["html"].read_text()
    store.close()
