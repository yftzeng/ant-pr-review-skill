"""Jurisdiction merge (D-PR-5): an independent merger call compares the per-jurisdiction
results once all are done, each jurisdiction's own reviewers answer its questions in
separate calls, then the merger writes the consolidated view. Verdicts are never
changed here (D-PR-11)."""
from __future__ import annotations

from . import prompts
from .backends.base import Backend, BackendError
from .jsonio import read_json, write_json
from .review import FAILED, OK, REFUSED, _parallel, _record
from .roster import slug
from .schemas import JCOMPARE, JDISCUSS, JFINAL
from .workspace import Run


def summary_for(syn: dict, j: str) -> dict:
    """The compact, computed view of one jurisdiction a model gets to see."""
    o = syn["jurisdictions"][j]
    return {"verdict": o["verdict"], "provisional": o["provisional"],
            "red_lines": {k: v["status"] for k, v in o["red_lines"].items()
                          if v["status"] not in ("clear",)},
            "risks": [{"id": r["id"], "unit": r["unit"], "dimension": r["dimension"],
                       "score": r["score"], "label": r["label"], "scenario": r["scenario"],
                       "standard": r["standard"], "legal_refs": r["legal_refs"]}
                      for r in o["risks"][:15] if r["scope"] == j],
            "failed_items": [{"item": i["item"], "verdict": i["verdict"], "label": i["label"]}
                             for i in o["items"] if i["verdict"] in ("concern", "fail")
                             and i["unit"].split(".")[0] == j],
            # POL-03 (sovereign red line): the panels' own quotes, so the merger never guesses
            "cross_region": [{"item": i["item"],
                              "evidence": [str(e)[:300] for e in i.get("evidence", {}).values()]}
                             for i in o["items"] if i["item"] == "POL-03"
                             and i["unit"].split(".")[0] == j]}


def reviewers_of(syn: dict, j: str) -> dict[str, list[str]]:
    """model -> lenses it held for jurisdiction j (from the units actually answered)."""
    out: dict[str, list[str]] = {}
    for u in syn["units"].values():
        if u["scope"] == j:
            for m in u["active"]:
                out.setdefault(m, [])
                out[m] += [ln for ln in u["lenses"] if ln not in out[m]]
    return out


def run_jmerge(run: Run, backend: Backend, merger: str, lang: str, *, say=print) -> dict | None:
    syn = read_json(run.path("06-synthesis.json"))
    js = list(syn["jurisdictions"])
    if len(js) < 2:
        write_json(run.path("07-jmerge/final.json"), {"skipped": "single_jurisdiction"})
        return None
    summaries = {j: summary_for(syn, j) for j in js}

    cmp_path = run.path("07-jmerge/compare.json")
    compare = read_json(cmp_path, default=None)
    if not compare or compare.get("status") not in (OK, REFUSED):
        say(f"  … compare ({merger})")
        compare = _record(merger, "jmerge", backend, lambda: backend.run(
            merger, task="jcompare", system=prompts.merger_system(lang),
            prompt=prompts.compare_prompt(summaries), schema=JCOMPARE))
        write_json(cmp_path, compare)
        if compare["status"] != OK:
            raise BackendError(f"merger compare: {compare.get('reason')}",
                               reason=compare.get("reason", "error"))
    questions = compare.get("data", {}).get("questions", [])

    jobs = []
    for j in js:
        qs = [q for q in questions if q["jurisdiction"].strip().lower() == j]
        if not qs:
            continue
        others = {k: v for k, v in summaries.items() if k != j}
        for m, lenses in reviewers_of(syn, j).items():
            p = run.path(f"07-jmerge/discuss/{j}/{slug(m)}.json")
            if read_json(p, default={}).get("status") in (OK, REFUSED):
                continue
            jobs.append((j, m, lenses, qs, others, p))

    def one(job):
        j, m, lenses, qs, others, p = job
        rec = _record(m, f"jmerge.{j}", backend, lambda: backend.run(
            m, task="jdiscuss", system=prompts.discuss_system(lang, lenses, j),
            prompt=prompts.discuss_prompt(j, qs, summaries[j], others), schema=JDISCUSS))
        rec["jurisdiction"] = j
        write_json(p, rec)
        say(f"  {'✓' if rec['status'] == OK else '✗'} discuss {j} · {m}: {rec['status']}")
        return rec

    _parallel(jobs, one)
    answers: dict[str, list] = {}
    d = run.path("07-jmerge/discuss")
    for p in sorted(d.glob("*/*.json")) if d.exists() else []:
        rec = read_json(p)
        if rec.get("status") == OK:
            answers.setdefault(rec["jurisdiction"], []).append(
                {"model": rec["model"], "answers": rec["data"]["answers"]})

    say(f"  … final ({merger})")
    final = _record(merger, "jmerge", backend, lambda: backend.run(
        merger, task="jfinal", system=prompts.merger_system(lang),
        prompt=prompts.final_prompt(summaries, compare.get("data", {}), answers), schema=JFINAL))
    final["merger"] = merger
    write_json(run.path("07-jmerge/final.json"), final)
    if final["status"] == FAILED:
        raise BackendError(f"merger final: {final.get('reason')}", reason=final.get("reason", "error"))
    return final

