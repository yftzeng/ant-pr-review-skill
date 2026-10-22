"""Round 1 (blind, per unit x model) and round 2 (cross-examination inside a unit).

Each (unit, model) is its own file, so a resumed phase calls only what is
missing or failed. Every checklist item of a unit must be answered by every
model (D-PR-3): a gap gets one targeted retry, then stays recorded as a gap.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from . import prompts
from .backends.base import Backend, BackendError
from .catalog import VERDICTS, red_lines_for
from .jsonio import read_json, write_json
from .roster import slug
from .schemas import DEBATE, review_schema
from .sources.segments import prompt_view
from .workspace import Run

OK, REFUSED, FAILED = "ok", "refused", "failed"
MAX_WORKERS = 6


def article_view(run: Run) -> str:
    segs = read_json(run.path("01-sources/segments.json"), default={})
    scan = read_json(run.path("01-sources/injection-scan.json"), default={})
    manifest = read_json(run.path("01-sources/manifest.json"), default={"items": []})
    origins = {d["doc"]: d.get("origin") or d.get("title") or ""
               for it in manifest["items"] for d in it.get("docs", [])}
    parts = []
    for doc, doc_segs in segs.items():
        parts.append(f"## Document {doc} {origins.get(doc, '')}".rstrip() + "\n\n"
                     + prompt_view(doc_segs, scan.get("withheld", {})))
    return "\n\n".join(parts)


def record_key(unit_id: str, model: str) -> str:
    return f"{unit_id}/{slug(model)}"


def load_records(run: Run, folder: str) -> dict[str, dict]:
    """'<unit>/<model-slug>' -> record, for every record file under folder."""
    d = run.path(folder)
    if not d.exists():
        return {}
    return {f"{p.parent.name}/{p.stem}": read_json(p) for p in sorted(d.glob("*/*.json"))}


def _record(model: str, unit: str, backend: Backend, fn) -> dict:
    base = {"model": model, "unit": unit, "backend": _backend_name(backend, model)}
    try:
        res = fn()
    except BackendError as e:
        return dict(base, status=FAILED, reason=e.reason, detail=str(e)[:500])
    if res.refused:
        return dict(base, model_id=res.model_id, status=REFUSED, reason="refused",
                    detail=res.refusal_detail, cost_usd=res.cost_usd)
    return dict(base, model_id=res.model_id, status=OK, data=res.data, cost_usd=res.cost_usd)


def _backend_name(backend: Backend, model: str) -> str:
    fn = getattr(backend, "backend_name", None)
    return fn(model) if fn else backend.name


def _clamp(v) -> int:
    try:
        return max(0, min(5, int(v)))
    except (TypeError, ValueError):
        return 0


def clean_review(data: dict, unit: dict) -> dict:
    """Clamp scales, keep only this unit's items once each, give risks unique ids."""
    allowed = set(unit["items"])
    seen, items = set(), []
    for c in data.get("checklist", []):
        if c["item"] in allowed and c["item"] not in seen and c["verdict"] in VERDICTS:
            seen.add(c["item"])
            items.append(dict(c, likelihood=_clamp(c["likelihood"]), impact=_clamp(c["impact"])))
    data["checklist"] = items
    ids = set()
    for n, r in enumerate(data.get("risks", []), 1):
        r["likelihood"], r["impact"] = max(1, _clamp(r["likelihood"])), max(1, _clamp(r["impact"]))
        if not r["id"] or r["id"] in ids:
            r["id"] = f"R{n}x"
        ids.add(r["id"])
    from .catalog import party_types_for
    seen_p, rows = set(), []
    if "stakeholders" in unit["lenses"]:
        allowed_p = set(party_types_for(unit["scope"]))
        for r in data.get("stakeholders", []) or []:
            if r.get("type") in allowed_p and r["type"] not in seen_p:
                seen_p.add(r["type"])
                rows.append(dict(r, likelihood=_clamp(r.get("likelihood")),
                                 impact=_clamp(r.get("impact")),
                                 relevance=r.get("relevance") if r.get("relevance")
                                 in ("none", "low", "high") else "none"))
    data["stakeholders"] = rows
    keys = set(red_lines_for(unit["items"]))
    data["red_lines"] = [rl for rl in data.get("red_lines", []) if rl["key"] in keys]
    return data


def missing_items(data: dict, unit: dict) -> list[str]:
    got = {c["item"] for c in data.get("checklist", [])}
    return [i for i in unit["items"] if i not in got]


def missing_types(data: dict, unit: dict) -> list[str]:
    from .catalog import party_types_for
    if "stakeholders" not in unit["lenses"]:
        return []
    got = {r["type"] for r in data.get("stakeholders", [])}
    return [p for p in party_types_for(unit["scope"]) if p not in got]


def _parallel(jobs: list, fn) -> list:
    if not jobs:
        return []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(jobs))) as ex:
        return list(ex.map(fn, jobs))


def run_round1(run: Run, backend: Backend, models: list[str], lang: str, *,
               say=print) -> dict[str, dict]:
    intake = read_json(run.path("00-intake.json"))
    matrix = read_json(run.path("03-matrix.json"))
    context = read_json(run.path("02-context.json"), default=None)
    article = article_view(run)
    existing = load_records(run, "04-reviews")
    jobs = [(u, m) for u in matrix["units"] for m in models
            if existing.get(record_key(u["id"], m), {}).get("status") not in (OK, REFUSED)]

    def one(job) -> dict:
        unit, m = job
        say(f"  … {unit['id']} · {m}")
        system = prompts.review_system(lang, unit)
        prompt = prompts.review_prompt(intake, unit, article, context)
        schema = review_schema()
        call = lambda p: backend.run(m, task="review", system=system, prompt=p, schema=schema)
        rec = _record(m, unit["id"], backend, lambda: call(prompt))
        if rec["status"] == OK:
            rec["data"] = clean_review(rec["data"], unit)
            gap, gap_t = missing_items(rec["data"], unit), missing_types(rec["data"], unit)
            if gap or gap_t:  # one targeted retry (D-PR-3), for items and party types
                again = _record(m, unit["id"], backend,
                                lambda: call(prompt + prompts.missing_items_prompt(gap, gap_t)))
                if again["status"] == OK:
                    again["data"] = clean_review(again["data"], unit)
                    # better only if neither checklist nor stakeholder answers got worse
                    if len(missing_items(again["data"], unit)) <= len(gap) and \
                            len(missing_types(again["data"], unit)) <= len(gap_t) and \
                            (len(missing_items(again["data"], unit)) < len(gap) or
                             len(missing_types(again["data"], unit)) < len(gap_t)):
                        rec = again
                rec["retried_for"] = gap + gap_t
            rec["unanswered"] = missing_items(rec["data"], unit)
            rec["unanswered_types"] = missing_types(rec["data"], unit)
        write_json(run.path(f"04-reviews/{unit['id']}/{slug(m)}.json"), rec)
        gap_note = f" · {len(rec.get('unanswered', []))} unanswered" if rec.get("unanswered") else ""
        say(f"  {'✓' if rec['status'] == OK else '✗'} {unit['id']} · {m}: {rec['status']}"
            + (f" ({rec.get('reason')})" if rec["status"] != OK else gap_note))
        return rec

    _parallel(jobs, one)
    return load_records(run, "04-reviews")


def debate_targets(recs: dict[str, dict], me: str) -> list[dict]:
    """Within one unit: the others' risks, red-line flags, and item verdicts that differ
    from mine."""
    mine = {c["item"]: c["verdict"] for c in recs.get(me, {}).get("data", {}).get("checklist", [])}
    out = []
    for m, rec in recs.items():
        if m == me or rec.get("status") != OK:
            continue
        s = slug(m)
        data = rec["data"]
        for r in data.get("risks", []):
            out.append({"target": f"{s}:{r['id']}", "anchor": r["anchor"], "item": r["item"],
                        "dimension": r["dimension"], "likelihood": r["likelihood"],
                        "impact": r["impact"], "scenario": r["scenario"],
                        "mitigation": r["mitigation"]})
        for rl in data.get("red_lines", []):
            if rl.get("flag"):
                out.append({"target": f"{s}:redline:{rl['key']}", "anchors": rl.get("anchors", []),
                            "severity": rl.get("severity"), "comment": rl.get("comment", "")})
        for c in data.get("checklist", []):
            if mine.get(c["item"]) is not None and mine[c["item"]] != c["verdict"]:
                out.append({"target": f"{s}:item:{c['item']}", "verdict": c["verdict"],
                            "your_verdict": mine[c["item"]], "evidence": c["evidence"]})
    return out


def unit_records(records: dict[str, dict], unit_id: str) -> dict[str, dict]:
    """model -> record, for one unit."""
    return {r["model"]: r for k, r in records.items() if k.split("/")[0] == unit_id}


def run_debate(run: Run, backend: Backend, models: list[str], lang: str, *,
               say=print) -> dict[str, dict]:
    matrix = read_json(run.path("03-matrix.json"))
    reviews = load_records(run, "04-reviews")
    ledger = read_ledger_safe(run)
    article = article_view(run)
    existing = load_records(run, "05-debate")
    jobs = []
    for unit in matrix["units"]:
        recs = unit_records(reviews, unit["id"])
        active = [m for m in models if recs.get(m, {}).get("status") == OK]
        if len(active) < 2:
            say(f"  ({unit['id']}: fewer than 2 reviewers answered, no debate)")
            continue
        for m in active:
            if existing.get(record_key(unit["id"], m), {}).get("status") not in (OK, REFUSED):
                jobs.append((unit, m, {k: recs[k] for k in active}))

    def one(job) -> dict:
        unit, m, recs = job
        prompt = prompts.debate_prompt(recs[m]["data"], debate_targets(recs, m), ledger, article)
        rec = _record(m, unit["id"], backend, lambda: backend.run(
            m, task="debate", system=prompts.debate_system(lang, unit), prompt=prompt,
            schema=DEBATE))
        write_json(run.path(f"05-debate/{unit['id']}/{slug(m)}.json"), rec)
        say(f"  {'✓' if rec['status'] == OK else '✗'} {unit['id']} · {m}: {rec['status']}")
        return rec

    _parallel(jobs, one)
    return load_records(run, "05-debate")


def read_ledger_safe(run: Run) -> list[dict]:
    from .factcheck import read_ledger
    return read_ledger(run)


def failed_jobs(records: dict[str, dict], units: list[dict], models: list[str]) -> list[str]:
    """'<unit> · <model>' for each (unit, model) without an ok or refused record."""
    return [f"{u['id']} · {m}" for u in units for m in models
            if records.get(record_key(u["id"], m), {}).get("status") not in (OK, REFUSED)]
