import networkx as nx

from psw import graph
from psw.pipeline import labels_for
from psw.triples import extract


def _graph(cases):
    triples = [t for c in cases for t in extract(c)]
    return graph.build_graph(triples, labels_for(cases))


def test_graph_nodes_have_kind_and_label(normalized):
    g = _graph(normalized)
    assert isinstance(g, nx.MultiDiGraph)
    assert g.nodes["person:244"]["kind"] == "Person"
    assert g.nodes["person:244"]["label"] == "Magnus Heunicke"
    assert g.nodes["party:UFG"]["kind"] == "Party"


def test_question_flows_count_party_to_addressee(normalized):
    flows = graph.question_flows(_graph(normalized))
    assert flows[("UFG", "Magnus Heunicke")] == 1
    # a question with no asker contributes no party flow
    assert not any(to == "Nicolai Wammen" and party for party, to in flows if party is None)


def test_topic_bridges_need_two_topics_per_person(normalized):
    # the fixture questions each have one or two topics; a bridge needs one person on two topics
    bridges = graph.topic_bridges(_graph(normalized))
    for b in bridges:
        assert b["topic_a"] != b["topic_b"]
        assert b["people"]


def test_topic_bridges_on_synthetic_graph():
    g = nx.MultiDiGraph()
    for node, kind in [("person:1", "Person"), ("case:1", "Case"), ("case:2", "Case"),
                       ("topic:a", "Topic"), ("topic:b", "Topic")]:
        g.add_node(node, kind=kind, label=node)
    g.nodes["person:1"]["label"] = "Ada"
    g.add_edge("person:1", "case:1", predicate="asked")
    g.add_edge("person:1", "case:2", predicate="asked")
    g.add_edge("case:1", "topic:a", predicate="has_topic")
    g.add_edge("case:2", "topic:b", predicate="has_topic")
    bridges = graph.topic_bridges(g)
    assert bridges == [{"topic_a": "topic:a", "topic_b": "topic:b", "people": ["Ada"]}]
