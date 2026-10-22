"""Domain catalog: lenses, risk dimensions, red lines, the checklist, jurisdiction
packs, and the review matrix (units) built from them."""
from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

PKG = Path(__file__).resolve().parent

DIRECTIONS = ["outbound", "operation", "inbound"]
# D-0002: the stance our communication takes, and the means a plan may use.
POSTURES = ["clarify_apologize", "promote", "expose", "rebut"]
DEFAULT_POSTURE = "clarify_apologize"
POSTURE_TEXT = {
    "clarify_apologize": "correct a misunderstanding or a false claim with facts we can "
                         "publish, and where we did wrong, own it and say how we fix it",
    "promote": "advertising, a campaign or building hype for us",
    "expose": "our own on-the-record disclosure of a named party's wrongdoing, on evidence we "
              "may lawfully use; leaking through unattributed third parties is a black means",
    "rebut": "answer a smear or false attack aimed at us",
}
# The first postures (before 2026-10-22) map onto the current ones.
LEGACY_POSTURES = {"clarify": "clarify_apologize", "apologize": "clarify_apologize",
                   "attack": "expose", "defend": "rebut"}
# D-0003: who we are in the event, and every party that reacts to it.
STANDPOINTS = ["responsible", "affected", "related"]
DEFAULT_STANDPOINTS = ["responsible"]
def _load_parties() -> list[dict]:
    return tomllib.loads((PKG / "parties.toml").read_text(encoding="utf-8"))["party"]


PARTIES = _load_parties()
PARTY_GROUPS: dict[str, list[str]] = {}
for _p in PARTIES:
    PARTY_GROUPS.setdefault(_p["group"], []).append(_p["key"])
PARTY_TYPES = [p["key"] for p in PARTIES]  # the base types; packs add their parties
PARTY_TEXT = {p["key"]: p["text"] for p in PARTIES}
GENERIC_POLITICS = ["ruling_party", "opposition_party"]
# A reasonable identity is a standpoint paired with a party type; astroturf never is.
# State and party organs of a pack are never an identity (D-0003).
VALID_IDENTITIES: dict[str, list[str]] = {
    "responsible": ["organization", "executives", "board", "staff", "implicated_individual",
                    "channel", "partners", "private_investors", "regulators", "ruling_party",
                    "opposition_party", "media", "kol", "community_leaders", "short_activists"],
    "affected": ["organization", "executives", "staff", "whistleblower",
                 "implicated_individual", "victims", "fans", "channel", "partners",
                 "private_investors", "public_investors", "lenders", "ruling_party",
                 "opposition_party", "media", "kol"],
    "related": ["organization", "executives", "board", "staff", "whistleblower", "channel",
                "partners", "private_investors", "public_investors", "lenders", "regulators",
                "opposing_counsel", "ruling_party", "opposition_party", "media", "kol",
                "community_leaders", "competitors", "short_activists"],
}
DEFAULT_IDENTITY = "responsible:organization"


def identity_options(standpoints: list[str]) -> list[str]:
    return [f"{sp}:{p}" for sp in STANDPOINTS if sp in standpoints
            for p in VALID_IDENTITIES[sp]]


MEANS = ["white", "gray", "black"]
MEANS_TEXT = {
    "white": "transparent, attributable and provable",
    "gray": "lawful but contested, only with disclosure (an exclusive to one outlet, "
            "newsjacking, comparative claims, timing a release, labelled sponsorship)",
    "black": "deceptive or unlawful (fake or borrowed identities, undisclosed paid posts, "
             "fabrication, doxxing, bought reviews)",
}

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
    "stakeholders": ("j", "the stakeholder map of this jurisdiction: how each party (inside "
                          "the company, the business chain, capital markets, authorities, "
                          "opinion, rivals) faces and handles this"),
}

DEFAULT_LENSES = {
    "outbound": ["legal", "journalist", "social", "target", "regulator", "internal",
                 "stakeholders"],
    "operation": ["legal", "journalist", "social", "regulator", "whistleblower", "stakeholders"],
    "inbound": ["threat", "legal", "social", "response", "stakeholders"],
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
    return tuple(validate_items(data["item"]))


def validate_items(items: list[dict]) -> list[dict]:
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
        if not set(i.get("postures", POSTURES)) <= set(POSTURES):
            raise ValueError(f"{i['id']}: unknown posture in {i['postures']}")
        if not set(i.get("roles", [])) <= set(PARTY_TYPES) | {"organization"}:
            raise ValueError(f"{i['id']}: unknown party type in {i['roles']}")
    return items


@lru_cache(maxsize=None)
def pack(code: str) -> dict:
    if code not in JURISDICTIONS:
        raise ValueError(f"unknown jurisdiction {code!r}; choose from {JURISDICTIONS}")
    return tomllib.loads((PKG / "jurisdictions" / f"{code}.toml").read_text(encoding="utf-8"))


def items_for(direction: str, lenses: list[str], posture: str = DEFAULT_POSTURE,
              identities: list[str] | None = None) -> list[dict]:
    """An item without `postures` is asked under every posture; an item with `roles` only
    when one of our identities has that party type (any standpoint)."""
    ours = {x.split(":", 1)[1] for x in (identities or [DEFAULT_IDENTITY])}
    return [i for i in checklist() if direction in i["directions"] and i["lens"] in lenses
            and posture in i.get("postures", POSTURES)
            and (not i.get("roles") or ours & set(i["roles"]))]


def unit_id(scope: str, lens: str) -> str:
    """'global.journalist', 'tw.legal', 'global.all', 'us.all'."""
    return f"{scope}.{lens}"


def plan_units(direction: str, lenses: list[str], jurisdictions: list[str],
               depth: str, posture: str = DEFAULT_POSTURE,
               identities: list[str] | None = None) -> list[dict]:
    """The matrix rows. Each unit: id, scope ('global' or a jurisdiction), lenses, items.
    A jurisdiction-scoped lens never shares a call with another jurisdiction (D-PR-5)."""
    if depth not in DEPTHS:
        raise ValueError(f"depth must be one of {DEPTHS}")
    if not jurisdictions:
        raise ValueError("at least one jurisdiction is needed")
    if posture not in POSTURES:
        raise ValueError(f"posture must be one of {POSTURES}")
    unknown = [ln for ln in lenses if ln not in LENSES]
    if unknown:
        raise ValueError(f"unknown lens(es): {unknown}")
    glob = [ln for ln in lenses if LENSES[ln][0] == "global"]
    scoped = [ln for ln in lenses if LENSES[ln][0] == "j"]
    units = []

    def add(scope: str, group: list[str], name: str) -> None:
        items = [i["id"] for i in items_for(direction, group, posture, identities)]
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


def pack_parties(code: str) -> list[dict]:
    return list(pack(code).get("party", [])) if code in JURISDICTIONS else []


def all_party_types() -> list[str]:
    """Every type any unit may ask about: the base types and every pack's parties."""
    return PARTY_TYPES + [p["key"] for j in JURISDICTIONS for p in pack_parties(j)]


def party_types_for(scope: str) -> list[str]:
    """The rows of a stakeholders unit: the base types, with the generic political rows
    replaced by the pack's own parties when it lists any."""
    own = [p["key"] for p in pack_parties(scope)]
    base = [p for p in PARTY_TYPES if not (own and p in GENERIC_POLITICS)]
    i = base.index("media") if "media" in base else len(base)  # politics sits before opinion
    return base[:i] + own + base[i:] if own else base


POLITICAL_IDENTITIES = {"ruling_party", "opposition_party"}
SIDE_OF = {"ruling_party": ("ruling",), "opposition_party": ("opposition", "legislature")}


def state_ruled(code: str) -> bool:
    """A jurisdiction whose ruling party is a party or state organ: there a political
    identity would make us that organ, which is never our role (D-0003)."""
    return any(p["side"] == "party_organ" for p in pack_parties(code))


def parties_on_side(code: str, generic: str) -> list[dict]:
    return [p for p in pack_parties(code) if p["side"] in SIDE_OF.get(generic, ())]


def party_info(key: str) -> dict:
    """The base entry, or a pack party as {key, group: politics, text, side, note, ...}."""
    for p in PARTIES:
        if p["key"] == key:
            return p
    for j in JURISDICTIONS:
        for p in pack_parties(j):
            if p["key"] == key:
                return {**p, "group": "politics", "text": f"{p['name_en']} ({p['name']}), "
                        f"{p['side']}: {p['note']}, as of {p['as_of']}",
                        "concerns": "", "viewpoint": ""}
    return {"key": key, "group": "", "text": key, "concerns": "", "viewpoint": ""}


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
            for year in ((s["year"],) if s.get("year") else (d.year - 1, d.year, d.year + 1)):
                try:
                    cand = date(year, m, dd)
                except ValueError:
                    continue
                if abs((cand - d).days) <= days:
                    out.append({"jurisdiction": j, "date": cand.isoformat(), "note": s["note"]})
    return out

# ---- the event assessment (D-0006) ----
# Observed signals, ticked by the user, by the grade they point to; the bottom lines make
# it grade I whatever else is ticked.
SIGNALS = {"national_trending": "I", "state_media": "I", "boycott": "I", "survival": "I",
           "platform_trending": "II", "multi_media": "II", "values_questioned": "II",
           "rumours": "II", "business_hit": "II",
           "social_spread": "III", "self_media": "III", "complaints_surge": "III",
           "local_reputation": "III",
           "small_spread": "IV", "scattered_reviews": "IV",
           "major_safety": "I", "major_illegal": "I", "minors": "I"}
BOTTOM_LINES = ["major_safety", "major_illegal", "minors"]
GRADES = ["I", "II", "III", "IV"]
OWNERS = {"I": "top_and_advisers", "II": "executives", "III": "management",
          "IV": "business_unit"}
ACTIVATION = {"I": "activate", "II": "activate", "III": "standby", "IV": "observe"}
# The three things people lose in a crisis and ask back (control: predictability,
# explicability, influence); each axis subtotals the items that answer it.
AXES = {"predictability": ["SOC-07", "JOU-06", "JOU-08", "JOU-16", "INT-07"],
        "explicability": ["JOU-17", "JOU-09", "LEG-14", "SOC-11", "CLR-01", "JOU-07"],
        "influence": ["APO-03", "APO-01", "INT-06", "JOU-15", "RSP-03"]}
