"""Turn raw ODA case records + actor records into flat, stable case dicts.

Only what the analysis needs is kept. Actor biographies in ODA contain phone
numbers and e-mail addresses; we keep a person's name and party short name only.
"""
from __future__ import annotations

import re

# SagAktørRolle ids (from /api/SagAktørRolle)
ROLE_BY = 4               # Af
ROLE_CO_ASKER = 5         # Medspørger
ROLE_MINISTRY = 6         # Ministerområde
ROLE_RELEVANT_FOR = 9     # Relevant for (committee)
ROLE_ASKER = 10           # Spørger
ROLE_REFERRED_TO = 11     # Henvist til (committee)
ROLE_MINISTER = 14        # Minister (minister title)
ROLE_PROPOSER_PRIV = 16   # Forslagsstiller (priv.)
ROLE_TO = 17              # Til (the person the question is put to)
ROLE_PROPOSER_GOV = 19    # Forslagsstiller (reg.)
ROLE_ANSWERED_BY = 23     # Besvaret af

KIND = {10: "question", 3: "bill"}

_PARTY = re.compile(r"<partyShortname>([^<]*)</partyShortname>")


def party_of(actor: dict) -> str | None:
    m = _PARTY.search(actor.get("biografi") or "")
    return (m.group(1).strip() or None) if m else None


def slim_actor(actor: dict) -> dict:
    return {"id": actor["id"], "name": actor["navn"], "typeid": actor["typeid"],
            "party": party_of(actor)}


def samling_label(kode: str | None) -> str | None:
    """ODA period code '20252' -> '2025/2' (the form Retsinformation uses)."""
    if not kode or len(kode) != 5:
        return None
    return f"{kode[:4]}/{kode[4]}"


def normalize_case(raw: dict, actors: dict[int, dict], statuses: dict[int, str],
                   periods: dict[int, str]) -> dict:
    by_role: dict[int, list[dict]] = {}
    for link in raw.get("SagAktør") or []:
        a = actors.get(link["aktørid"])
        if a is not None:
            by_role.setdefault(link["rolleid"], []).append(slim_actor(a))
    for people in by_role.values():
        people.sort(key=lambda p: p["id"])

    def first(role):
        return (by_role.get(role) or [None])[0]

    return {
        "id": raw["id"],
        "kind": KIND.get(raw["typeid"], f"type{raw['typeid']}"),
        "number": raw.get("nummer"),
        "samling": samling_label(periods.get(raw.get("periodeid"))),
        "title": raw.get("titel"),
        "short_title": raw.get("titelkort"),
        "status": statuses.get(raw.get("statusid"), f"status{raw.get('statusid')}"),
        "updated": raw.get("opdateringsdato"),
        "ministry": first(ROLE_MINISTRY),
        "minister_title": first(ROLE_MINISTER),
        "askers": by_role.get(ROLE_ASKER, []),
        "co_askers": by_role.get(ROLE_CO_ASKER, []),
        "to": first(ROLE_TO),
        "answered_by": first(ROLE_ANSWERED_BY),
        "proposers": by_role.get(ROLE_PROPOSER_GOV, []) + by_role.get(ROLE_PROPOSER_PRIV, []),
        "committees": sorted({c["name"] for r in (ROLE_RELEVANT_FOR, ROLE_REFERRED_TO)
                              for c in by_role.get(r, [])}),
        "topics": sorted({(e.get("Emneord") or {}).get("emneord", "").strip().lower()
                          for e in raw.get("EmneordSag") or []} - {""}),
        "document_ids": sorted(d["dokumentid"] for d in raw.get("SagDokument") or []),
        "law_number": raw.get("lovnummer"),
        "law_date": (raw.get("lovnummerdato") or "")[:10] or None,
    }


def actor_ids(raw_cases: list[dict]) -> set[int]:
    return {link["aktørid"] for c in raw_cases for link in c.get("SagAktør") or []}
