from psw.triples import extract


def _set(triples):
    return {(t.subject, t.predicate, t.object) for t in triples}


def test_question_triples(normalized):
    got = _set(extract(normalized[0]))
    assert ("person:21369", "asked", "case:106155") in got          # Emilie Schytte asked S 40
    assert ("person:21369", "member_of", "party:UFG") in got
    assert ("case:106155", "directed_to", "person:244") in got      # S 40 directed to Heunicke
    assert ("person:244", "member_of", "party:S") in got
    assert ("case:106155", "concerns_ministry", "org:21449") in got


def test_every_triple_points_to_a_field(normalized):
    for c in normalized:
        for t in extract(c):
            assert t.source.startswith(f"case:{c['id']}/")


def test_no_asker_means_no_asked_triple(normalized):
    got = _set(extract(normalized[1]))
    assert not any(p == "asked" for _, p, _ in got)
    assert ("case:106329", "directed_to", "person:12") in got


def test_bill_triples(normalized):
    got = _set(extract(normalized[2]))
    assert ("case:71032", "concerns_law", "law:866") in got
    assert any(p == "referred_to" for _, p, _ in got)
