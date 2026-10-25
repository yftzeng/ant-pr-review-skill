"""Company profile (D-0004): the official registry first, then competitors found by a
search-capable model, graded by their sources and ticked by the user. The registry's
personal data (the representative's name, the address) is dropped on read."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from urllib.parse import quote

from . import prompts
from .backends.base import Backend, BackendError
from .factcheck import _provenance_filter
from .i18n import T
from .roster import can_search
from .schemas import PROFILE_SEARCH
from .sources.crawler import FetchError
from .sources.grade import OFFICIAL, host as _host, outlet as _outlet
from .ui import checkbox, confirm

GCIS = "https://data.gcis.nat.gov.tw/od/data/api/{ds}?$format=json&$filter={flt}&$skip=0&$top=1"
DATASETS = {"basic": "5F64D864-61CB-4D0D-8AD9-492047CC1EA6",
            "items": "236EE382-4942-41A9-BD03-CA0709025E7C"}
# Letter sections of Taiwan's business-item codes (營業項目代碼).
SECTIONS = {"A": "agriculture", "B": "mining", "C": "manufacturing", "D": "utilities",
            "E": "construction", "F": "wholesale_retail", "G": "transport_comms",
            "H": "finance_real_estate", "I": "professional_services", "J": "culture_leisure",
            "Z": "other"}
GRADE = {"registry": "A", "regulator": "A", "exchange_filing": "A", "independent": "B",
         "company_claim": "C", "aggregator": "C", "lead": "C"}
MAX_COMPETITORS = 12


def valid_tax_id(s: str) -> bool:
    """8 ASCII digits (not all zero) and the checksum: the weighted digit sum divisible by 5
    (the 2023 rule, which also accepts every ID valid under the old divisible-by-10 rule),
    or that sum plus one when the 7th digit is 7."""
    s = (s or "").strip()
    if not re.fullmatch(r"[0-9]{8}", s) or s == "00000000":
        return False
    total = sum(p // 10 + p % 10 for p in (int(d) * w for d, w in zip(s, (1, 2, 1, 2, 1, 2, 4, 1))))
    return total % 5 == 0 or (s[6] == "7" and (total + 1) % 5 == 0)


def _roc(d: str) -> str:
    d = (d or "").strip()
    if re.fullmatch(r"[0-9]{7}", d) and int(d[:3]) > 0:
        try:
            return date(int(d[:3]) + 1911, int(d[3:5]), int(d[5:])).isoformat()
        except ValueError:
            return ""
    return ""


def _get(crawler, ds: str, tax_id: str) -> tuple[list, dict]:
    url = GCIS.format(ds=DATASETS[ds], flt=quote(f"Business_Accounting_NO eq {tax_id}"))
    res = crawler.fetch(url, types=("application/json", "text/plain", "text/html"))
    raw = res.body.decode("utf-8-sig", "replace").strip()
    data = json.loads(raw) if raw else []  # GCIS answers an empty body for an unknown ID
    if not isinstance(data, list) or any(not isinstance(r, dict) for r in data):
        raise ValueError("unexpected registry answer")  # an error object is not absence
    return data, {"dataset": ds, "url": url, "accessed_at": date.today().isoformat()}


def registry_lookup(crawler, tax_id: str) -> dict:
    """Facts kept: name, status, set-up date, capital, registering office, business items
    (N-company-profile-001: no representative, no address)."""
    if not valid_tax_id(tax_id):
        return {"status": "invalid", "tax_id": tax_id}
    try:
        basic, s1 = _get(crawler, "basic", tax_id)
        items, s2 = _get(crawler, "items", tax_id)
    except (FetchError, ValueError) as e:
        return {"status": "error", "tax_id": tax_id,
                "reason": getattr(e, "reason", "") or type(e).__name__}
    if not basic:
        return {"status": "not_found", "tax_id": tax_id, "sources": [s1],
                "checked": f"GCIS company registry, {s1['accessed_at']}"}
    b = basic[0]
    biz = []
    for row in items:
        rows = row.get("Cmp_Business") or []
        for x in rows if isinstance(rows, list) else []:
            code = str(x.get("Business_Item", "")).strip() if isinstance(x, dict) else ""
            if code:  # free-text rows without a code are no industry
                biz.append({"code": code, "desc": str(x.get("Business_Item_Desc", ""))[:80]})
    biz = biz[:40]
    sections = list(dict.fromkeys(SECTIONS.get(i["code"][:1], "other") for i in biz if i["code"]))
    return {"status": "found", "tax_id": tax_id, "sources": [s1, s2],
            "facts": {"name": str(b.get("Company_Name", "")),
                      "status": str(b.get("Company_Status_Desc", "")),
                      "set_up": _roc(str(b.get("Company_Setup_Date", ""))),
                      "capital": b.get("Capital_Stock_Amount"),
                      "registered_with": str(b.get("Register_Organization_Desc", "")),
                      "business_items": biz, "industries": sections}}


ROLES = ("direct", "indirect", "substitute", "benchmark")


def _clean_name(s) -> str:
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[\x00-\x1f\x7f\u200b-\u200f\u2028\u2029]", " ", s)
    s = re.sub(r"[\[\]{}<>\"`|\\]", "", s)
    return " ".join(s.split())[:80]


def grade_competitors(raw: list[dict], tool_results: list[str]) -> list[dict]:
    """Only evidence whose URL a search returned counts. An official grade (A) needs an
    official host; otherwise it is a claim (C). One outlet is one source, keeping its best
    grade. Duplicate names merge. Confirmed with one A or two B from different outlets."""
    merged: dict[str, dict] = {}
    for c in raw:
        if not isinstance(c, dict):
            continue
        name = _clean_name(c.get("name"))
        if not name:
            continue
        m = merged.setdefault(name.casefold(), {"name": name, "role": c.get("role"),
                                                "evidence": []})
        m["evidence"] += [e for e in c.get("evidence", []) if isinstance(e, dict)]
    out = []
    for m in list(merged.values())[:MAX_COMPETITORS]:
        best: dict[str, dict] = {}
        for e in _provenance_filter(m["evidence"], tool_results):
            grade = GRADE.get(e.get("kind", "lead"), "C")
            if grade == "A" and not OFFICIAL.search(_host(e["url"])):
                grade = "C"  # an official kind on a non-official host is only a claim
            item = {"url": e["url"], "kind": e.get("kind", "lead"), "grade": grade,
                    "excerpt": str(e.get("excerpt", ""))[:300]}
            o = _outlet(e["url"])
            if o not in best or item["grade"] < best[o]["grade"]:
                best[o] = item
        kept = list(best.values())
        if not kept:
            continue
        grades = [e["grade"] for e in kept]
        out.append({"name": m["name"], "role": m["role"] if m["role"] in ROLES else "indirect",
                    "status": "confirmed" if "A" in grades or grades.count("B") >= 2
                    else "lead", "evidence": kept})
    return sorted(out, key=lambda c: c["status"] != "confirmed")


def build_profile(card: dict, crawler, backend: Backend, models: list[str], lang: str, *,
                  io, interactive: bool, allowed: bool, say=print) -> dict:
    t = T(lang)
    tax_id, org = str(card.get("tax_id", "") or "").strip(), str(card.get("org", "") or "")
    # a skipped lookup clears what an earlier one wrote into the card
    out = {"status": "skipped", "registry": {}, "competitors": [], "errors": [],
           "card": {"industry": [], "competitors": []}}
    if not tax_id and not org:
        return out
    if tax_id and not valid_tax_id(tax_id):
        out["registry"] = {"status": "invalid", "tax_id": tax_id[:20]}
        say(f"  {t('profile.registry', status=t('profile.reg.invalid'))}")
        return out
    # Under embargo only a fresh, interactive yes counts (D-0004, D-PR-9): --company-lookup
    # alone never sends anything for embargoed material.
    if card.get("embargo") or not allowed:
        if not interactive:
            return out
        q = t("profile.confirm_embargo" if card.get("embargo") else "profile.confirm",
              what=tax_id or org)
        if not confirm(io, t, q, default=not card.get("embargo")):
            return out
    out["status"] = "done"
    if tax_id:
        out["registry"] = registry_lookup(crawler, tax_id)
        say(f"  {t('profile.registry', status=t('profile.reg.' + out['registry']['status']))}")
    facts = out["registry"].get("facts", {})
    name = facts.get("name") or org
    searcher = next((m for m in models if can_search(m)), None)
    if name and searcher:
        try:
            res = backend.run(searcher, task="profile", system=prompts.profile_system(lang),
                              prompt=prompts.profile_prompt(name, facts, card.get("jurisdictions", [])),
                              schema=PROFILE_SEARCH, tools=("WebSearch",), effort="medium")
            if res.refused or not res.data:
                out["errors"].append("search refused")
            else:
                out["competitors"] = grade_competitors(res.data.get("competitors", []),
                                                       res.tool_results)
        except BackendError as e:
            out["errors"].append(f"search: {e.reason}")
    comps = out["competitors"]
    if interactive and comps:
        opts = [(c["name"], f"{c['name']} ({t('profile.' + c['status'])}, "
                 f"{'/'.join(e['grade'] for e in c['evidence'])})") for c in comps]
        ticked = checkbox(io, t, t("profile.pick"), opts,
                          [c["name"] for c in comps if c["status"] == "confirmed"])
    else:
        ticked = [c["name"] for c in comps if c["status"] == "confirmed"]
    out["card"] = {"industry": facts.get("industries", []), "competitors": ticked}
    return out
