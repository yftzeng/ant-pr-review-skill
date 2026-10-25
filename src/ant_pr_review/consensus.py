"""Deterministic synthesis (D-PR-6, D-PR-11): item tallies, merged risks, red lines and
a verdict per jurisdiction; the consolidated verdict is the worst of them.

No model call happens here, so recomputing after a fact-check change or a ruling is
free. Labels come only from the tally of positions; silence is not agreement.
"""
from __future__ import annotations

from .catalog import RED_LINES, VERDICT_RANK, item_index
from .roster import slug, vendors
from .sources.grade import is_evidence

RL_SEV = {"none": 0, "low": 1, "medium": 2, "high": 3}
VETO_MIN_SEV = RL_SEV["medium"]
VERDICT_ORDER = ["go", "conditional", "escalate", "no_go"]


class _UF:
    def __init__(self, items):
        self.p = {i: i for i in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _by_unit(records: dict[str, dict]) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for key, rec in records.items():
        out.setdefault(key.split("/")[0], {})[rec["model"]] = rec
    return out


def _responses(debates: dict[str, dict], active: list[str]) -> list[tuple[str, dict]]:
    out = []
    for m in active:
        rec = debates.get(m, {})
        if rec.get("status") == "ok":
            for r in rec["data"].get("responses", []):
                out.append((m, r))
    return out


def tally_items(unit: dict, recs: dict[str, dict], active: list[str],
                resp: list[tuple[str, dict]]) -> list[dict]:
    out = []
    for item in unit["items"]:
        by_model, unanswered = {}, []
        for m in active:
            got = [c for c in recs[m]["data"].get("checklist", []) if c["item"] == item]
            if got:
                by_model[m] = got[0]
            else:
                unanswered.append(m)
        verdicts = {m: c["verdict"] for m, c in by_model.items()}
        worst = max(verdicts.values(), key=lambda v: VERDICT_RANK[v], default="unanswered")
        distinct = set(verdicts.values())
        if len(distinct) > 1:
            label = "SPLIT"
        elif verdicts:
            label = f"AGREE-{len(verdicts)}/{len(active)}"
        else:
            label = "UNANSWERED"
        targets = {f"{slug(m)}:item:{item}" for m in active}
        notes = [{"model": w, "position": r["position"], "target": r["target"],
                  "evidence": r.get("evidence", "")}
                 for w, r in resp if r["target"] in targets]
        scores = [c["likelihood"] * c["impact"] for c in by_model.values()
                  if c["verdict"] in ("concern", "fail")]
        out.append({"item": item, "unit": unit["id"], "verdict": worst, "label": label,
                    "by_model": verdicts, "unanswered": unanswered,
                    "score": max(scores, default=0),
                    "evidence": {m: c["evidence"] for m, c in by_model.items()},
                    "anchors": sorted({a for c in by_model.values() for a in c["anchors"]}),
                    "notes": notes})
    return out


REL_RANK = {"none": 0, "low": 1, "high": 2}


def tally_stakeholders(unit: dict, recs: dict[str, dict], active: list[str]) -> list[dict]:
    """D-0003: every party type, each model's answer; a missing type is a gap."""
    from .catalog import party_info, party_types_for
    if "stakeholders" not in unit["lenses"]:
        return []
    out = []
    for p in party_types_for(unit["scope"]):
        by_model, unanswered = {}, []
        for m in active:
            got = [r for r in recs[m]["data"].get("stakeholders", []) if r.get("type") == p]
            if got:
                by_model[m] = got[0]
            else:
                unanswered.append(m)
        out.append({"type": p, "group": party_info(p)["group"], "unit": unit["id"],
                    "relevance": max((a.get("relevance", "none") for a in by_model.values()),
                                     key=lambda v: REL_RANK.get(v, 0), default="none"),
                    "score": max((int(a.get("likelihood") or 0) * int(a.get("impact") or 0)
                                  for a in by_model.values()), default=0),
                    "by_model": by_model, "unanswered": unanswered})
    return out


def merge_risks(unit: dict, recs: dict[str, dict], active: list[str],
                resp: list[tuple[str, dict]], ref_to_claim: dict[str, dict]) -> list[dict]:
    risks = {f"{slug(m)}:{r['id']}": dict(r, model=m)
             for m in active for r in recs[m]["data"].get("risks", [])}
    uf = _UF(risks)
    for who, r in resp:
        dup = (r.get("duplicate_of") or "").strip()
        if r["position"] == "corroborate" and dup and r["target"] in risks:
            mine = f"{slug(who)}:{dup}"
            if mine in risks:
                uf.union(r["target"], mine)
    groups: dict[str, list[str]] = {}
    for gid in risks:
        groups.setdefault(uf.find(gid), []).append(gid)
    n = len(active)
    out = []
    for members in groups.values():
        members.sort(key=lambda g: (active.index(risks[g]["model"]), g))
        owners = {risks[g]["model"] for g in members}
        corrob = {w for w, r in resp if r["target"] in members and r["position"] == "corroborate"}
        disputes = [{"model": w, "evidence": r.get("evidence", "")} for w, r in resp
                    if r["target"] in members and r["position"] == "dispute" and w not in owners]
        supporters = sorted(owners | corrob, key=active.index)
        if disputes:
            label = "SPLIT"
        elif len(supporters) == n and n >= 2:
            label = f"CONSENSUS-{n}"
        elif len(supporters) >= 2:
            label = f"CORROBORATED-{len(supporters)}/{n}"
        else:
            label = "SINGLE"
        lead = risks[members[0]]
        ls = [risks[g]["likelihood"] for g in members]
        im = [risks[g]["impact"] for g in members]
        L, I = max(ls), max(im)
        rk = unit["id"]
        claims = [ref_to_claim.get(f"{rk}/{slug(risks[g]['model'])}:{k}")
                  for g in members for k in risks[g].get("claim_ids", [])]
        weak = sorted({c["id"] for c in claims if c and c["status"] == "cannot_verify"})
        f = {"members": members, "unit": rk, "scope": unit["scope"], "label": label,
             "supporters": supporters, "dissent": disputes, "anchor": lead["anchor"],
             "item": lead.get("item", ""), "dimension": lead["dimension"],
             "scenario": lead["scenario"], "standard": lead["standard"],
             "why_it_matters": lead["why_it_matters"], "mitigation": lead["mitigation"],
             "legal_refs": sorted({x for g in members for x in risks[g].get("legal_refs", [])}),
             "likelihood": L, "impact": I, "score": L * I,
             "spread": {"likelihood": max(ls) - min(ls), "impact": max(im) - min(im)},
             "wide": max(ls) - min(ls) >= 2 or max(im) - min(im) >= 2}
        # An unprovable statement is itself the provability risk, so it is never set aside.
        if weak and f["dimension"] != "provability":
            f["unverified_claims"] = weak
        out.append(f)
    return out


def red_line_flags(recs: dict[str, dict], active: list[str], resp: list[tuple[str, dict]],
                   key: str) -> dict:
    flaggers, advisory, sev, comments = [], [], 0, []
    for m in active:
        for rl in recs[m]["data"].get("red_lines", []):
            if rl["key"] == key and rl.get("flag"):
                s = RL_SEV.get(rl.get("severity", "none"), 0)
                (flaggers if s >= VETO_MIN_SEV else advisory).append(m)
                sev = max(sev, s)
                comments.append({"model": m, "comment": rl.get("comment", ""),
                                 "anchors": rl.get("anchors", [])})
    tgt = {f"{slug(m)}:redline:{key}" for m in flaggers}
    corrob = {w for w, r in resp if r["target"] in tgt and r["position"] == "corroborate"}
    disputes = [{"model": w, "evidence": r.get("evidence", "")} for w, r in resp
                if r["target"] in tgt and r["position"] == "dispute" and w not in flaggers]
    return {"flaggers": flaggers, "advisory": advisory, "corrob": corrob, "dissent": disputes,
            "severity": sev, "comments": comments}


def rule_red_line(key: str, parts: list[dict], ledger: list[dict], ruling: str | None) -> dict:
    flaggers = {m for p in parts for m in p["flaggers"]}
    supporters = sorted(flaggers | {m for p in parts for m in p["corrob"]})
    disputes = [d for p in parts for d in p["dissent"] if d["model"] not in flaggers]
    advisory = {m for p in parts for m in p["advisory"]}
    sev = max((p["severity"] for p in parts), default=0)
    evidence, weak = [], []
    if key == "fabrication_about_party":
        for c in ledger:
            if c["type"] == "allegation" and c["status"] == "unsupported":
                # S-review-matrix-033: only C sources behind it cannot outrank a dispute
                (evidence if is_evidence(c) else weak).append({"claim": c["id"],
                                                               "text": c["text"]})
    if not supporters:
        status = "advisory" if advisory else "clear"
    elif evidence:
        status = "confirmed"          # evidence first: the ledger outranks a dispute
    elif len(supporters) >= 2 and not disputes:
        status = "confirmed"
    else:
        status = "needs_ruling"
    ruled = False
    if ruling and status == "needs_ruling":
        status, ruled = ruling, True
    return {"status": status, "supporters": supporters, "dissent": disputes,
            "severity": [s for s, v in RL_SEV.items() if v == sev][0],
            "comments": [c for p in parts for c in p["comments"]], "evidence": evidence,
            "weak_evidence": weak, "human_ruling": ruled}


def verdict_for(red: dict, risks: list[dict], items: list[dict], th: dict) -> dict:
    if any(v["status"] == "confirmed" for v in red.values()):
        verdict = "no_go"
    else:
        top = max([r["score"] for r in risks] + [i["score"] for i in items], default=0)
        legal = max([r["score"] for r in risks if r["dimension"] == "legal"], default=0)
        if top >= th["escalate"] or legal >= th["escalate_legal"]:
            verdict = "escalate"
        elif top >= th["conditional"]:
            verdict = "conditional"
        else:
            verdict = "go"
    return {"verdict": verdict,
            "provisional": any(v["status"] == "needs_ruling" for v in red.values())}


def counsel_questions(risks: list[dict], th: dict) -> list[str]:
    """Escalate: the concrete legal questions for a lawyer (D-PR-13)."""
    return [f"{r['id']}: {r['standard']} — {r['scenario']}"
            for r in risks if r["dimension"] == "legal" and r["score"] >= th["escalate_legal"]]


def synthesize(*, matrix: dict, reviews: dict[str, dict], debates: dict[str, dict],
               ledger: list[dict], models: list[str], thresholds: dict[str, float],
               rulings: dict[str, str] | None = None) -> dict:
    rulings = rulings or {}
    rev_u, deb_u = _by_unit(reviews), _by_unit(debates)
    ref_to_claim = {ref: c for c in ledger for ref in c.get("refs", [])}
    warnings = []
    if len(vendors(models)) == 1:
        warnings.append("single_vendor")

    provenance = []
    for m in models:
        st = [rev_u.get(u["id"], {}).get(m, {}).get("status", "missing") for u in matrix["units"]]
        rec = next((rev_u[u["id"]][m] for u in matrix["units"]
                    if m in rev_u.get(u["id"], {})), {})
        provenance.append({"model": m, "vendor": vendors([m])[0], "backend": rec.get("backend", ""),
                           "model_id": rec.get("model_id", ""),
                           "ok": st.count("ok"), "refused": st.count("refused"),
                           "failed": len(st) - st.count("ok") - st.count("refused")})

    per_unit = {}
    for unit in matrix["units"]:
        recs = rev_u.get(unit["id"], {})
        active = [m for m in models if recs.get(m, {}).get("status") == "ok"]
        if len(active) < 2 and "fewer_than_two_reviewers" not in warnings:
            warnings.append("fewer_than_two_reviewers")
        resp = _responses(deb_u.get(unit["id"], {}), active)
        per_unit[unit["id"]] = {
            "unit": unit, "active": active,
            "items": tally_items(unit, recs, active, resp),
            "risks": merge_risks(unit, recs, active, resp, ref_to_claim),
            "red": {k: red_line_flags(recs, active, resp, k) for k in RED_LINES},
            "headlines": [h for m in active for h in recs[m]["data"].get("worst_headlines", [])],
            "stakeholders": tally_stakeholders(unit, recs, active),
        }

    # stable ids across the whole run, highest score first
    all_risks = [r for pu in per_unit.values() for r in pu["risks"]]
    key = lambda r: (-r["score"], r["unit"], r["anchor"])
    kept = sorted([r for r in all_risks if "unverified_claims" not in r], key=key)
    unver = sorted([r for r in all_risks if "unverified_claims" in r], key=key)
    for i, r in enumerate(kept, 1):
        r["id"] = f"R{i:02d}"
    for i, r in enumerate(unver, 1):
        r["id"] = f"U{i:02d}"

    idx = item_index()
    jurisdictions = matrix["jurisdictions"]
    out_j = {}
    for j in jurisdictions:
        units = [pu for pu in per_unit.values() if pu["unit"]["scope"] in ("global", j)]
        risks = sorted([r for pu in units for r in pu["risks"] if "unverified_claims" not in r],
                       key=key)
        items = [i for pu in units for i in pu["items"]]
        red = {}
        for k in RED_LINES:
            ruling = rulings.get(f"{j}:{k}") or rulings.get(k)
            red[k] = rule_red_line(k, [pu["red"][k] for pu in units], ledger, ruling)
        v = verdict_for(red, risks, items, thresholds)
        out_j[j] = {**v, "red_lines": red, "risks": risks,
                    "unverified": sorted([r for pu in units for r in pu["risks"]
                                          if "unverified_claims" in r], key=key),
                    "items": sorted(items, key=lambda i: list(idx).index(i["item"])),
                    "unanswered": [{"item": i["item"], "unit": i["unit"], "models": i["unanswered"]}
                                   for i in items if i["unanswered"]],
                    "headlines": [h for pu in units for h in pu["headlines"]],
                    "stakeholders": [r for pu in units for r in pu["stakeholders"]],
                    "counsel_questions": counsel_questions(risks, thresholds)
                    if v["verdict"] == "escalate" else []}
    if any(o["unanswered"] for o in out_j.values()):
        warnings.append("unanswered_items")
    if any(r["unanswered"] for o in out_j.values() for r in o.get("stakeholders", [])):
        warnings.append("unanswered_party_types")
    worst = max((o["verdict"] for o in out_j.values()), key=VERDICT_ORDER.index)
    return {"provenance": provenance, "warnings": warnings, "direction": matrix["direction"],
            "jurisdictions": out_j,
            "consolidated": {"verdict": worst,
                             "worst": [j for j, o in out_j.items() if o["verdict"] == worst],
                             "provisional": any(o["provisional"] for o in out_j.values())},
            "units": {u: {"active": pu["active"], "scope": pu["unit"]["scope"],
                          "lenses": pu["unit"]["lenses"]} for u, pu in per_unit.items()},
            "risks": kept, "unverified": unver}
