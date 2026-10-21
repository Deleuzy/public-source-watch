import copy
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample():
    """Three real ODA records (saved offline): a question with a named addressee, an
    unanswered-asker question with no askers, and a bill that became a law."""
    return json.loads((FIXTURES / "oda_sample.json").read_text())


@pytest.fixture
def normalized(sample):
    from psw.normalize import normalize_case

    actors = {int(k): v for k, v in sample["actors"].items()}
    statuses = {s["id"]: s["status"] for s in sample["statuses"]}
    periods = {p["id"]: p["kode"] for p in sample["periods"]}
    return [normalize_case(c, actors, statuses, periods) for c in sample["cases"]]


@pytest.fixture
def changed_copy(normalized):
    """The same cases one run later: S 40 changes status, and one new question appears."""
    later = copy.deepcopy(normalized)
    later[0]["status"] = "Besvaret, endeligt-test"
    new = copy.deepcopy(normalized[1])
    new["id"] = 999999
    new["number"] = "S 999"
    later.append(new)
    return later
