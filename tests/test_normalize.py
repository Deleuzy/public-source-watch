from psw.normalize import party_of, samling_label


def test_question_roles_are_mapped(normalized):
    q = normalized[0]  # S 40
    assert q["kind"] == "question"
    assert q["number"] == "S 40"
    assert [a["name"] for a in q["askers"]] == ["Emilie Schytte"]
    assert q["askers"][0]["party"] == "UFG"
    assert q["to"]["name"] == "Magnus Heunicke"
    assert q["to"]["party"] == "S"
    assert q["ministry"]["name"] == "Undervisningsministeriet"


def test_no_asker_is_empty_not_error(normalized):
    q = normalized[1]  # S 130 has no asker link in ODA
    assert q["askers"] == []
    assert q["to"]["name"] == "Nicolai Wammen"


def test_bill_gets_law_number_and_committee(normalized):
    bill = normalized[2]  # L 23, lov nr. 866
    assert bill["kind"] == "bill"
    assert bill["law_number"] == "866"
    assert bill["law_date"] == "2026-10-07"
    assert "Klima-, Energi- og Forsyningsudvalget" in bill["committees"]


def test_samling_label_matches_retsinformation_form():
    assert samling_label("20252") == "2025/2"
    assert samling_label("20261") == "2026/1"
    assert samling_label(None) is None


def test_party_parsed_from_biography_only():
    assert party_of({"biografi": "<member><partyShortname>UFG</partyShortname></member>"}) == "UFG"
    assert party_of({"biografi": None}) is None
    assert party_of({"biografi": "<member><partyShortname></partyShortname></member>"}) is None
