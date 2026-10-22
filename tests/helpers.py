"""Scriptable backend and canned reviewer outputs for pipeline tests."""
from ant_pr_review.backends.base import Backend, BackendError, Result
from ant_pr_review.catalog import plan_units, red_lines_for
from ant_pr_review.jsonio import write_json
from ant_pr_review.roster import slug
from ant_pr_review.workspace import create_run

M1, M2, M3 = "claude:opus", "openai:gpt-5", "grok:grok-4"


def risk(rid="R1", **kw):
    r = {"id": rid, "anchor": "D1.P01.S1", "item": "", "dimension": "backlash",
         "scenario": "scn", "standard": "std", "why_it_matters": "why", "mitigation": "mit",
         "likelihood": 2, "impact": 2, "legal_refs": [], "claim_ids": []}
    r.update(kw)
    return r


def review_data(items=(), verdicts=None, risks=(), claims=(), flags=(), headlines=(),
                red_keys=None, low=()):
    """items: the unit's checklist ids, all answered "pass" unless verdicts overrides
    (item -> verdict or (verdict, L, I)); a verdict of None leaves the item out."""
    verdicts = verdicts or {}
    checklist = []
    for i in items:
        v = verdicts.get(i, "pass")
        if v is None:
            continue
        v, L, I = (v, 0, 0) if isinstance(v, str) else v
        checklist.append({"item": i, "verdict": v, "likelihood": L, "impact": I,
                          "anchors": ["D1.P01.S1"], "evidence": "ev"})
    keys = red_keys if red_keys is not None else red_lines_for(list(items))
    keys = list(dict.fromkeys(list(keys) + list(flags) + list(low)))
    return {
        "orientation": "A short piece.",
        "checklist": checklist,
        "risks": [risk(**r) if isinstance(r, dict) else r for r in risks],
        "claims": [dict({"id": "K1", "anchor": "D1.P02.S1", "text": "Revenue grew 40% in 2025",
                         "type": "number"}, **c) for c in claims],
        "red_lines": [{"key": k, "flag": k in flags or k in low,
                       "severity": "high" if k in flags else ("low" if k in low else "none"),
                       "anchors": [], "comment": "c" if k in flags else ""} for k in keys],
        "worst_headlines": list(headlines),
    }


def ok(model, unit, data):
    return {"model": model, "unit": unit, "model_id": f"id-{model}", "status": "ok", "data": data,
            "backend": "test"}


def recs(*pairs):
    """[(unit, model, data)] -> records keyed like load_records."""
    return {f"{u}/{slug(m)}": ok(m, u, d) for u, m, d in pairs}


def deb(model, unit, *responses):
    return {f"{unit}/{slug(model)}": {"model": model, "unit": unit, "status": "ok", "data": {
        "responses": [dict({"evidence": "", "duplicate_of": ""}, **r) for r in responses]}}}


class ScriptBackend(Backend):
    """handlers: {(model, task): fn(prompt) -> Result | dict | Exception | list}.
    A list is consumed one answer per call."""
    name = "script"

    def __init__(self, handlers=None, default=None):
        self.handlers = handlers or {}
        self.default = default
        self.calls = []

    def run(self, model, *, task, system, prompt, schema, tools=(), effort="high", timeout=900):
        self.calls.append({"model": model, "task": task, "prompt": prompt, "system": system,
                           "tools": tools, "schema": schema})
        h = self.handlers.get((model, task)) or self.handlers.get(("*", task)) or self.default
        if isinstance(h, list):
            h = h.pop(0) if len(h) > 1 else h[0]
        out = h(prompt) if callable(h) else h
        if isinstance(out, Exception):
            raise out
        if isinstance(out, Result):
            out.model, out.model_id = model, f"id-{model}"
            return out
        return Result(model=model, model_id=f"id-{model}", data=out)


def make_run(tmp_path, text="# Title\n\nFirst para.\n\nRevenue grew 40% in 2025. Second.",
             models=(M1, M2), jurisdictions=("tw",), depth="quick", direction="outbound",
             lenses=None, card=None):
    from ant_pr_review.catalog import DEFAULT_LENSES
    from ant_pr_review.sources.acquire import run_sources
    run = create_run(tmp_path / "runs", "t", models=list(models), backend="script", lang="en")
    c = {"org": "", "parties": [], "jurisdictions": list(jurisdictions), "channels": [],
         "stakeholders": [], "publish_at": "", "keywords": [], "embargo": False}
    c.update(card or {})
    write_json(run.path("00-intake.json"), {"direction": direction,
                                            "targets": [{"kind": "text", "value": text}],
                                            "card": c, "lang": "en"})
    run_sources(run, crawler=None)
    write_json(run.path("02-context.json"), {"status": "skipped", "queries": [], "findings": [],
                                             "errors": [], "sensitive_dates": []})
    lenses = list(lenses or DEFAULT_LENSES[direction])
    units = plan_units(direction, lenses, list(jurisdictions), depth)
    write_json(run.path("03-matrix.json"), {"direction": direction, "depth": depth,
                                            "lenses": lenses, "jurisdictions": list(jurisdictions),
                                            "units": units, "models": list(models),
                                            "merger": models[0]})
    return run


def unit_items(run, unit_id):
    from ant_pr_review.jsonio import read_json
    return next(u for u in read_json(run.path("03-matrix.json"))["units"]
                if u["id"] == unit_id)["items"]


def auto_review(verdicts=None, **kw):
    """A review handler that answers every item of the unit it is asked about."""
    import re

    def h(prompt):
        items = re.findall(r"^- ([A-Z]{3}-\d{2}) \[", prompt, re.M)
        data = review_data(items=items, verdicts=verdicts, **kw)
        if "EVERY party type" in prompt:  # a stakeholders unit (D-0003)
            data["stakeholders"] = [{"type": p, "relevance": "low", "reaction": "r",
                                     "needs": "n", "handling": "h", "likelihood": 1,
                                     "impact": 1}
                                    for p in re.findall(r"^   - ([a-z_]+): ", prompt, re.M)]
        return data
    return h


__all__ = ["BackendError", "M1", "M2", "M3"]
