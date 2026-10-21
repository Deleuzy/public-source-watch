"""Build a networkx MultiDiGraph from triples and answer journalist questions."""
from __future__ import annotations

from collections import Counter
from itertools import combinations

import networkx as nx

from .triples import Triple

KIND_LABEL = {"person": "Person", "party": "Party", "case": "Case", "org": "Ministry",
              "topic": "Topic", "law": "Law", "committee": "Committee"}


def build_graph(triples: list[Triple], labels: dict[str, str] | None = None) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for t in triples:
        for node in (t.subject, t.object):
            if node not in g:
                kind = node.split(":", 1)[0]
                g.add_node(node, kind=KIND_LABEL.get(kind, kind),
                           label=(labels or {}).get(node, node))
        g.add_edge(t.subject, t.object, predicate=t.predicate, source=t.source)
    return g


def question_flows(g: nx.MultiDiGraph) -> Counter:
    """(asker party, minister/person addressed) -> number of questions.

    A question counts once per (asking party, addressee) pair, so a question with
    several askers from one party is not counted twice for that party.
    """
    flows: Counter = Counter()
    for case in (n for n, d in g.nodes(data=True) if d["kind"] == "Case"):
        addressees = [v for _, v, d in g.out_edges(case, data=True) if d["predicate"] == "directed_to"]
        if not addressees:
            continue
        parties = set()
        for asker, _, d in g.in_edges(case, data=True):
            if d["predicate"] != "asked":
                continue
            for _, party, pd in g.out_edges(asker, data=True):
                if pd["predicate"] == "member_of":
                    parties.add(party)
        for party in parties:
            for to in addressees:
                flows[(g.nodes[party]["label"], g.nodes[to]["label"])] += 1
    return flows


def topic_bridges(g: nx.MultiDiGraph, top_n: int = 10) -> list[dict]:
    """People who asked about two different topics.

    For each pair of topics the people who asked about both are listed, and pairs
    are ranked by how many people bridge them. Only the `top_n` most used topics
    are considered so the result stays readable.
    """
    person_topics: dict[str, set[str]] = {}
    topic_use: Counter = Counter()
    for u, v, d in g.edges(data=True):
        if d["predicate"] != "asked":
            continue
        for _, topic, td in g.out_edges(v, data=True):
            if td["predicate"] == "has_topic":
                person_topics.setdefault(u, set()).add(topic)
    for topics in person_topics.values():
        topic_use.update(topics)
    keep = {t for t, _ in topic_use.most_common(top_n)}

    pair_people: dict[tuple, list[str]] = {}
    for person, topics in person_topics.items():
        for a, b in combinations(sorted(topics & keep), 2):
            pair_people.setdefault((a, b), []).append(person)
    ranked = sorted(pair_people.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return [{"topic_a": g.nodes[a]["label"], "topic_b": g.nodes[b]["label"],
             "people": sorted(g.nodes[p]["label"] for p in people)}
            for (a, b), people in ranked]
