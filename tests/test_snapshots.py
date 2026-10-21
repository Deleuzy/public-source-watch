from datetime import datetime

from psw.snapshots import SnapshotStore, content_hash, diff_cases


def test_hash_is_stable_and_order_free(normalized):
    c = normalized[0]
    assert content_hash(c) == content_hash(dict(reversed(list(c.items()))))


def test_first_run_has_no_previous(tmp_path, normalized):
    store = SnapshotStore(tmp_path / "s.sqlite")
    assert store.previous_run_id() is None  # nothing stored yet, so nothing to compare with
    r1 = store.save_run(normalized, source="test", days=1, started_at=datetime(2026, 10, 21, 9))
    assert store.previous_run_id(r1) is None  # the only run has no earlier run


def test_diff_reports_added_changed_and_removed(tmp_path, normalized, changed_copy):
    store = SnapshotStore(tmp_path / "s.sqlite")
    r1 = store.save_run(normalized, source="test", days=1)
    r2 = store.save_run(changed_copy, source="test", days=1)
    assert store.previous_run_id(r2) == r1

    diff = diff_cases(store.cases_of(r1), store.cases_of(r2))
    assert [c["number"] for c in diff["added"]] == ["S 999"]
    assert diff["removed"] == []
    assert len(diff["changed"]) == 1
    ch = diff["changed"][0]
    assert ch["case"]["number"] == "S 40"
    assert ch["fields"] == ["status"]
    assert ch["after"]["status"] == "Besvaret, endeligt-test"
    store.close()


def test_identical_runs_have_no_changes(tmp_path, normalized):
    store = SnapshotStore(tmp_path / "s.sqlite")
    r1 = store.save_run(normalized, source="test", days=1)
    r2 = store.save_run(normalized, source="test", days=1)
    diff = diff_cases(store.cases_of(r1), store.cases_of(r2))
    assert diff == {"added": [], "changed": [], "removed": []}
    store.close()


def test_removed_case_is_reported(normalized):
    old = {c["id"]: c for c in normalized}
    new = {k: v for k, v in old.items() if k != normalized[2]["id"]}
    assert [c["number"] for c in diff_cases(old, new)["removed"]] == ["L 23"]
