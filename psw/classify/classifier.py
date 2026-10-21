"""Rule-based placement of normalised cases in the org tree (ministry -> area)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class Placement:
    case_id: int
    ministry: str
    ministry_rule: str | None
    area: str
    area_rule: str | None


class Classifier:
    def __init__(self, org_path: Path = HERE / "org.yaml", rules_path: Path = HERE / "rules.yaml"):
        self.org = yaml.safe_load(Path(org_path).read_text())
        rules = yaml.safe_load(Path(rules_path).read_text())
        self.ministry_rules = rules["ministry_rules"]
        self.area_rules = rules["area_rules"]
        self.ministries = {m["id"]: m for m in self.org["ministries"]}

    def nodes(self) -> list[dict]:
        out = []
        for m in self.org["ministries"]:
            out.append({"id": m["id"], "name": m["name"], "source": m.get("source")})
            out += [{"id": a["id"], "name": a["name"], "source": a.get("source")} for a in m["areas"]]
        return out

    def names(self) -> dict[str, str]:
        return {n["id"]: n["name"] for n in self.nodes()} | {UNCLASSIFIED: "Unclassified"}

    def classify(self, case: dict) -> Placement:
        ministry, m_rule = self._ministry(case)
        area, a_rule = self._area(case, ministry) if ministry != UNCLASSIFIED else (UNCLASSIFIED, None)
        return Placement(case["id"], ministry, m_rule, area, a_rule)

    def _ministry(self, case: dict) -> tuple[str, str | None]:
        actor = case.get("ministry") or {}
        for rule in self.ministry_rules:
            if actor.get("id") == rule["ministry_id"]:
                return rule["assign"], rule["id"]
        return UNCLASSIFIED, None

    def _area(self, case: dict, ministry: str) -> tuple[str, str | None]:
        topics = [t.lower() for t in case.get("topics") or []]
        title = (case.get("title") or "").lower()
        for rule in self.area_rules:
            if rule.get("by") == "emneord":
                for area in self.ministries[ministry]["areas"]:
                    exact = set(area.get("emneord") or [])
                    prefixes = tuple(area.get("emneord_prefix") or [])
                    if any(t in exact or (prefixes and t.startswith(prefixes)) for t in topics):
                        return area["id"], rule["id"]
            elif rule.get("ministry") == ministry and any(k in title for k in rule["title_contains"]):
                return rule["assign"], rule["id"]
        return UNCLASSIFIED, None
