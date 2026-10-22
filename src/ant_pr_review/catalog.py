"""Domain catalog: lenses, risk dimensions, red lines, the checklist, jurisdiction
packs, and the review matrix (units) built from them."""
from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

PKG = Path(__file__).resolve().parent

DIRECTIONS = ["outbound", "operation", "inbound"]

# key -> (scope, seat description). scope "j" = one unit per jurisdiction.
LENSES: dict[str, tuple[str, str]] = {
    "legal": ("j", "legal counsel for this jurisdiction: test each element of each law, and "
                   "the defenses (truth, reasonable verification, fair comment)"),
    "journalist": ("global", "a hostile investigative journalist: the story is us, not our "
                             "message; you also judge timing"),
    "social": ("j", "the online communities of this jurisdiction: what gets screenshotted, "
                    "memed, doxxed or boycotted"),
    "target": ("global", "the named party and its lawyer: how you answer, what you can prove, "
                         "whether you sue"),
    "regulator": ("j", "the regulators of this jurisdiction and platform trust-and-safety "
                       "teams"),
    "internal": ("global", "our employees, investors and partners"),
    "whistleblower": ("global", "an insider or contractor who leaks this plan"),
    "threat": ("global", "a threat analyst breaking hostile content into allegations; you "
                         "never identify the people behind accounts"),
    "response": ("global", "a crisis-response adviser comparing response options"),
}

DEFAULT_LENSES = {
    "outbound": ["legal", "journalist", "social", "target", "regulator", "internal"],
    "operation": ["legal", "journalist", "social", "regulator", "whistleblower"],
    "inbound": ["threat", "legal", "social", "response"],
}

DIMENSIONS = ["legal", "provability", "disclosure", "attribution", "backlash", "platform",
              "stakeholder", "timing", "ethics"]

RED_LINES = ["fabrication_about_party", "undisclosed_inauthentic", "privacy_doxxing",
             "election_law", "market_manipulation", "health_claims", "hate_human_rights",
             "illegal_other"]

RED_LINE_TEXT = {
    "fabrication_about_party": "a fabricated or unprovable statement of fact about a named "
                               "person, company or agency",
    "undisclosed_inauthentic": "fake or borrowed identities, sockpuppets, paid posters, fake "
                               "reviews or undisclosed paid endorsement",
    "privacy_doxxing": "exposing a private individual or personal data without a lawful basis",
    "election_law": "rumours, polls, ads or campaigning that breach election rules",
    "market_manipulation": "false or misleading information that can move a market price",
    "health_claims": "prohibited health, medical, food or drug effect claims",
    "hate_human_rights": "demeaning or stereotyping a protected group",
    "illegal_other": "other content or conduct that is illegal in this jurisdiction",
}

JURISDICTIONS = ["tw", "us", "eu", "cn"]
DEFAULT_JURISDICTIONS = ["tw"]
DEPTHS = ["quick", "full"]

VERDICTS = ["pass", "concern", "fail", "na"]
VERDICT_RANK = {"na": 0, "pass": 1, "concern": 2, "fail": 3}


def _check_unique(ids: list[str], what: str) -> None:
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"duplicate {what} ids: {dup}")


@lru_cache(maxsize=None)
def checklist() -> tuple[dict, ...]:
    data = tomllib.loads((PKG / "checklists" / "default.toml").read_text(encoding="utf-8"))
    items = data["item"]
    _check_unique([i["id"] for i in items], "checklist")
    for i in items:
        if i["lens"] not in LENSES:
            raise ValueError(f"{i['id']}: unknown lens {i['lens']}")
        if i["dimension"] not in DIMENSIONS:
            raise ValueError(f"{i['id']}: unknown dimension {i['dimension']}")
        if i.get("red_line") and i["red_line"] not in RED_LINES:
            raise ValueError(f"{i['id']}: unknown red line {i['red_line']}")
        if not set(i["directions"]) <= set(DIRECTIONS):
            raise ValueError(f"{i['id']}: unknown direction in {i['directions']}")
    return tuple(items)


@lru_cache(maxsize=None)
def pack(code: str) -> dict:
    if code not in JURISDICTIONS:
        raise ValueError(f"unknown jurisdiction {code!r}; choose from {JURISDICTIONS}")
    return tomllib.loads((PKG / "jurisdictions" / f"{code}.toml").read_text(encoding="utf-8"))


def items_for(direction: str, lenses: list[str]) -> list[dict]:
    return [i for i in checklist() if direction in i["directions"] and i["lens"] in lenses]


def unit_id(scope: str, lens: str) -> str:
    """'global.journalist', 'tw.legal', 'global.all', 'us.all'."""
    return f"{scope}.{lens}"


def plan_units(direction: str, lenses: list[str], jurisdictions: list[str],
               depth: str) -> list[dict]:
    """The matrix rows. Each unit: id, scope ('global' or a jurisdiction), lenses, items.
    A jurisdiction-scoped lens never shares a call with another jurisdiction (D-PR-5)."""
    if depth not in DEPTHS:
        raise ValueError(f"depth must be one of {DEPTHS}")
    if not jurisdictions:
        raise ValueError("at least one jurisdiction is needed")
    unknown = [ln for ln in lenses if ln not in LENSES]
    if unknown:
        raise ValueError(f"unknown lens(es): {unknown}")
    glob = [ln for ln in lenses if LENSES[ln][0] == "global"]
    scoped = [ln for ln in lenses if LENSES[ln][0] == "j"]
    units = []

    def add(scope: str, group: list[str], name: str) -> None:
        items = [i["id"] for i in items_for(direction, group)]
        if items:
            units.append({"id": unit_id(scope, name), "scope": scope, "lenses": group,
                          "items": items})

    if depth == "quick":
        add("global", glob, "all")
        for j in jurisdictions:
            add(j, scoped, "all")
    else:
        for ln in glob:
            add("global", [ln], ln)
        for j in jurisdictions:
            for ln in scoped:
                add(j, [ln], ln)
    return units


def item_index() -> dict[str, dict]:
    return {i["id"]: i for i in checklist()}


def red_lines_for(items: list[str]) -> list[str]:
    """The red lines a unit is asked about: those its items can support, plus
    illegal_other whenever a legal item is in the unit."""
    idx = item_index()
    keys = {idx[i]["red_line"] for i in items if idx[i].get("red_line")}
    if any(idx[i]["lens"] == "legal" for i in items):
        keys.add("illegal_other")
    return [k for k in RED_LINES if k in keys]


def sensitive_dates_near(jurisdictions: list[str], publish_at: str, days: int = 3) -> list[dict]:
    """Pack dates within +-days of an ISO publish date (no web needed)."""
    from datetime import date
    try:
        d = date.fromisoformat(publish_at.strip()[:10])
    except ValueError:
        return []
    out = []
    for j in jurisdictions:
        for s in pack(j).get("sensitive_date", []):
            m, dd = (int(x) for x in s["md"].split("-"))
            for year in (d.year - 1, d.year, d.year + 1):
                try:
                    cand = date(year, m, dd)
                except ValueError:
                    continue
                if abs((cand - d).days) <= days:
                    out.append({"jurisdiction": j, "date": cand.isoformat(), "note": s["note"]})
    return out
