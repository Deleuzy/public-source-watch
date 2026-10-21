"""Rule-based triple extraction from normalized cases.

Every rule reads one structured field, so each triple can be traced back to a
case id and a field name (see `Triple.source`). No LLM is used.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Triple:
    subject: str
    predicate: str
    object: str
    source: str  # e.g. "case:106378/askers"


def case_node(case: dict) -> str:
    return f"case:{case['id']}"


def person_node(actor: dict) -> str:
    return f"person:{actor['id']}"


def party_node(party: str) -> str:
    return f"party:{party}"


def ministry_node(actor: dict) -> str:
    return f"org:{actor['id']}"


def topic_node(topic: str) -> str:
    return f"topic:{topic}"


def law_node(law_number: str) -> str:
    return f"law:{law_number}"


def committee_node(name: str) -> str:
    return f"committee:{name}"


def extract(case: dict) -> list[Triple]:
    """All triples for one case. Labels for nodes are added separately in graph.py."""
    cid = case_node(case)
    out: list[Triple] = []

    def add(s, p, o, field):
        out.append(Triple(s, p, o, f"case:{case['id']}/{field}"))

    for a in case["askers"]:
        add(person_node(a), "asked", cid, "askers")
        if a.get("party"):
            add(person_node(a), "member_of", party_node(a["party"]), "askers")
    for a in case["co_askers"]:
        add(person_node(a), "co_asked", cid, "co_askers")
        if a.get("party"):
            add(person_node(a), "member_of", party_node(a["party"]), "co_askers")
    for p in case["proposers"]:
        add(person_node(p), "proposed", cid, "proposers")
        if p.get("party"):
            add(person_node(p), "member_of", party_node(p["party"]), "proposers")
    for role, field in ((case["to"], "to"), (case["answered_by"], "answered_by")):
        if not role:
            continue
        if field == "to":
            add(cid, "directed_to", person_node(role), "to")
        else:
            add(cid, "answered_by", person_node(role), "answered_by")
        if role.get("party"):
            add(person_node(role), "member_of", party_node(role["party"]), field)
    if case["ministry"]:
        add(cid, "concerns_ministry", ministry_node(case["ministry"]), "ministry")
    for t in case["topics"]:
        add(cid, "has_topic", topic_node(t), "topics")
    for c in case["committees"]:
        add(cid, "referred_to", committee_node(c), "committees")
    if case["law_number"]:
        add(cid, "concerns_law", law_node(case["law_number"]), "law_number")
    return out
