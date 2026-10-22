"""Deterministic offline backend: `--backend fake` for demos and smoke tests.

It never calls a model. Outputs are schema-valid and anchored to ids found in
the prompt, so the whole pipeline can be exercised without network or cost.
"""
from __future__ import annotations

import re

from ..catalog import RED_LINES, all_party_types
from .base import Backend, Result


def _ids(prompt: str) -> list[str]:
    return re.findall(r"\[(D[\w-]+\.P\d+(?:\.S\d+)?)\]", prompt)


def _para_ids(prompt: str) -> list[str]:
    seen = []
    for i in _ids(prompt):
        p = ".".join(i.split(".")[:2])
        if p not in seen:
            seen.append(p)
    return seen


class FakeBackend(Backend):
    name = "fake"

    def run(self, model, *, task, system, prompt, schema, tools=(), effort="high",
            timeout=900) -> Result:
        ids = _ids(prompt) or ["D1.P01"]
        paras = _para_ids(prompt) or ["D1.P01"]
        bias = sum(map(ord, model)) % 3
        data = getattr(self, f"_{task}")(model, ids, paras, bias, prompt, schema)
        calls, results = [], []
        if tools:
            calls = [{"name": "WebSearch", "input": {"query": "fake"}}]
            results = ["Links: https://example.org/fake-source"]
        return Result(model=model, model_id=f"fake-{model}", data=data, cost_usd=0.0,
                      tool_calls=calls, tool_results=results)

    def _probe(self, *a):
        return {"ok": True}

    def _review(self, model, ids, paras, bias, prompt, schema):
        items = re.findall(r"^- ([A-Z]{3}-\d{2}) \[", prompt, re.M)
        keys = [k for k in RED_LINES if re.search(rf"^- {k}: ", prompt, re.M)]
        first, last = ids[0], ids[-1]
        checklist = []
        for n, i in enumerate(items):
            v = "concern" if n == 0 else "pass"
            checklist.append({"item": i, "verdict": v, "likelihood": 2 + bias if v != "pass" else 0,
                              "impact": 3 if v != "pass" else 0, "anchors": [first],
                              "evidence": f"[fake:{model}] {i}"})
        return {
            "orientation": f"[fake:{model}] The material has {len(paras)} paragraphs.",
            "checklist": checklist,
            "risks": [{"id": "R1", "anchor": last, "item": items[0] if items else "",
                       "dimension": "backlash", "scenario": "A sentence is quoted out of context.",
                       "standard": "Statements should survive being quoted alone.",
                       "why_it_matters": "Screenshots travel without context.",
                       "mitigation": "Rephrase the sentence so it stands alone.",
                       "likelihood": 2 + bias, "impact": 3, "legal_refs": [], "claim_ids": []}],
            "claims": [{"id": "K1", "anchor": first, "text": "The first sentence states a fact.",
                        "type": "other"}],
            "red_lines": [{"key": k, "flag": False, "severity": "none", "anchors": [],
                           "comment": ""} for k in keys],
            "worst_headlines": [f"[fake:{model}] Company under fire"],
            "stakeholders": [{"type": p, "relevance": "low", "reaction": f"[fake:{model}] watches",
                              "needs": "facts", "handling": "brief them on the record",
                              "likelihood": 1, "impact": 2}
                             for p in re.findall(r"^   - ([a-z_]+): ", prompt, re.M)
                             if p in all_party_types()],
        }

    def _factcheck(self, *a):
        return {"status": "supported", "reason": "fake",
                "sources": [{"url": "https://example.org/fake-source",
                             "supporting_excerpt": "fake excerpt"}]}

    def _profile(self, *a):
        return {"competitors": [{"name": "[fake] Rival Co", "role": "direct", "evidence": [
            {"url": "https://example.org/fake-source", "kind": "regulator", "excerpt": "fake"}]}]}

    def _context(self, *a):
        return {"findings": [{"summary": "fake news item", "url": "https://example.org/fake-source",
                              "date": "2026-10-01", "relevance": "low"}]}

    def _draft(self, model, ids, paras, bias, prompt, schema):
        lead = {"who": "we", "what": "a fault", "when": "today", "where": "our service",
                "why": "under investigation", "how": "replacement"}

        def v(approach, order):
            parts = {"stance": "We are sorry that the fault affected you.",
                     "facts": "Today we confirmed a fault in our service.",
                     "cause": "The cause is still under investigation.",
                     "measures": "Stop using it; we replace it free from Monday at 10:00."}
            return {"approach": approach, "title": f"[fake:{model}] Statement",
                    "paragraphs": [{"text": parts[k], "part": k} for k in order],
                    "lead_5w1h": lead,
                    "claims": [{"text": "a fault in our service", "basis": ["C1"],
                                "class": "public"}]}
        return {"versions": [v("apology first", ["stance", "facts", "cause", "measures"]),
                             v("action first", ["measures", "facts", "stance", "cause"])],
                "blocking_questions": [], "contradictions": []}

    def _draft_review(self, *a):
        return {"versions": [{"version": "V1", "issues": []},
                             {"version": "V2", "issues": []}]}

    def _draft_reason(self, *a):
        return {"reason": "[fake] It ranks first on its verdict and a 90% pass rate."}

    def _debate(self, model, ids, paras, bias, prompt, schema):
        targets = re.findall(r'"target": "([^"]+)"', prompt)
        return {"responses": [{"target": t, "position": "corroborate", "evidence": "same",
                               "duplicate_of": "R1"} for t in targets if t.endswith(":R1")]}

    def _jcompare(self, model, ids, paras, bias, prompt, schema):
        js = sorted(set(re.findall(r'"(tw|us|eu|cn)": \{', prompt)))
        return {"differences": [{"topic": "fake difference",
                                 "by_jurisdiction": [{"jurisdiction": j, "position": "fake"}
                                                     for j in js]}],
                "questions": [{"id": f"Q{n}", "jurisdiction": j, "question": "fake question?"}
                              for n, j in enumerate(js, 1)]}

    def _jdiscuss(self, model, ids, paras, bias, prompt, schema):
        qs = re.findall(r'"id": "(Q\d+)"', prompt)
        return {"answers": [{"question": q, "answer": "fake answer", "revised": False,
                             "revision": ""} for q in qs]}

    def _jfinal(self, model, ids, paras, bias, prompt, schema):
        js = sorted(set(re.findall(r'"(tw|us|eu|cn)": \{', prompt)))
        return {"summary": "fake consolidated view", "common_risks": ["fake common risk"],
                "differences": [{"topic": "fake difference",
                                 "by_jurisdiction": [{"jurisdiction": j, "position": "fake"}
                                                     for j in js]}],
                "strictest": js[0] if js else "", "notes": [{"jurisdiction": j, "note": "fake"}
                                                           for j in js]}

    def _plan_a(self, model, ids, paras, bias, prompt, schema):
        return {"paragraphs": [{"id": paras[-1], "text": "[fake edit] A sentence that stands "
                                "alone."}], "corrections": []}

    def _timeline(self, model, ids, paras, bias, prompt, schema):
        step = lambda day, time, action, cat: {"day": day, "time": time, "action": action,
                                               "category": cat, "channel": "website",
                                               "notes": "[fake]", "trigger": "", "stop": "",
                                               "audience": "public", "paid": False}
        return {"steps": [step(0, "09:00", "[fake] Publish the statement", "white"),
                          step(1, "10:00", "[fake] Disclosed briefing for one outlet", "gray")],
                "excluded": [{"tactic": "[fake] undisclosed paid posts", "why": "deceives readers",
                              "law": "[fake]", "exposure": "journalists and platform reports",
                              "watch_for": "a wave of new accounts",
                              "lawful_alternative": "a named spokesperson"}]}

    def _classify_means(self, model, ids, paras, bias, prompt, schema):
        n = len(re.findall(r'"step": \d+', prompt))
        return {"labels": [{"step": i, "category": "white" if i == 1 else "gray", "reason": "fake"}
                           for i in range(1, n + 1)], "excluded_flags": []}

    def _plan_b(self, model, ids, paras, bias, prompt, schema):
        props = schema["properties"]
        if "alternative_plan" in props:
            return {"recommendation": "transparent_alternative",
                    "alternative_plan": "[fake] Announce it with a named spokesperson.",
                    "rationale": "fake", "addresses": ["R01"]}
        if "options" in props:
            return {"options": [{"option": "clarify", "when": "now", "risks": "fake",
                                 "addresses": ["R01"]}],
                    "recommended": "clarify", "statement_draft": "[fake] Our statement."}
        return {"recommendation": "publish_revised", "headline_options": ["A calmer headline"],
                "paragraphs": [{"id": paras[-1], "text": "[fake rewrite] A sentence that stands "
                                "alone.", "addresses": ["R01"]}], "alternative": "", "notes": "fake"}

    def _kit(self, *a):
        return {"holding_statement": "[fake] We are aware and will update.",
                "qa": [{"question": "What happened?", "answer": "[fake] Only provable facts."}],
                "monitoring_keywords": [{"term": "fake", "kind": "brand", "platforms": ["PTT"]}],
                "escalation": [{"trigger": "media call", "action": "route to PR lead",
                                "owner": "PR lead"}], "do_not_say": ["no comment"]}

    def _rereview(self, model, ids, paras, bias, prompt, schema):
        found = sorted(set(re.findall(r'"id": "(R\d+)"', prompt)))
        return {"verdicts": [{"issue": f, "verdict": "FULLY", "note": "fake"} for f in found]}
