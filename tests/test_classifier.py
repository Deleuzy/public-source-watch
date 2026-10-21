import json
from pathlib import Path

import pytest

from psw.classify.classifier import UNCLASSIFIED, Classifier
from psw.classify.report import summarise, write

FIXTURE = Path(__file__).parent / "fixtures" / "sample_cases.json"


@pytest.fixture
def cases():
    return {c["id"]: c for c in json.loads(FIXTURE.read_text())}


@pytest.fixture
def clf():
    return Classifier()


def test_every_org_node_has_a_source_url(clf):
    for node in clf.nodes():
        assert (node["source"] or "").startswith("https://oda.ft.dk/"), node


def test_rules_only_assign_nodes_that_exist(clf):
    ids = {n["id"] for n in clf.nodes()}
    assert {r["assign"] for r in clf.ministry_rules} <= ids
    assert {r["assign"] for r in clf.area_rules if "assign" in r} <= ids


def test_ministry_comes_from_the_oda_ministry_actor(clf, cases):
    assert clf.classify(cases[105498]).ministry == "oda-46"
    assert clf.classify(cases[105902]).ministry == "oda-17076"


def test_area_from_oda_keyword(clf, cases):
    p = clf.classify(cases[105902])
    assert (p.area, p.area_rule) == ("immigration-residence-asylum", "A1")
    assert clf.classify(cases[105732]).area == "immigration-integration"


def test_law_reference_is_used_when_no_keyword_matches(clf, cases):
    case = dict(cases[105732], topics=["arbejdsforhold 7a"])
    p = clf.classify(case)
    assert (p.area, p.area_rule) == ("immigration-residence-asylum", "A2")


def test_case_outside_the_two_ministries_is_unclassified(clf, cases):
    p = clf.classify(cases[105869])
    assert (p.ministry, p.area, p.ministry_rule) == (UNCLASSIFIED, UNCLASSIFIED, None)


def test_case_matching_no_area_rule_lands_in_unclassified(clf, cases):
    case = dict(cases[105498], topics=["punktafgifter"], title="Spørgsmål om noget helt andet")
    p = clf.classify(case)
    assert p.ministry == "oda-46" and p.area == UNCLASSIFIED and p.area_rule is None


def test_report_shows_unclassified_counts(clf, cases, tmp_path):
    s = write(7, list(cases.values()), clf, tmp_path / "data", tmp_path / "reports")
    assert s["unclassified_ministry"] == 1
    assert sum(s["by_ministry"].values()) == len(cases)
    md = (tmp_path / "reports" / "classification-run7.md").read_text()
    assert "No ministry rule matched (outside the two ministries in org.yaml): 1" in md
    rows = (tmp_path / "data" / "run-7.jsonl").read_text().splitlines()
    assert len(rows) == len(cases)


def test_summary_counts_area_gaps_separately(clf, cases):
    odd = dict(cases[105498], id=1, topics=["punktafgifter"], title="x")
    s = summarise([clf.classify(c) for c in [*cases.values(), odd]])
    assert s["unclassified_area"] == 1 and s["unclassified_ministry"] == 1
