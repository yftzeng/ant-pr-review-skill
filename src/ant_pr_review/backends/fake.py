"""Deterministic offline backend: `--backend fake` for demos and smoke tests.

It never calls a model. Outputs are schema-valid and anchored to ids found in
the prompt, so the whole pipeline can be exercised without network or cost.
"""
from __future__ import annotations

import re

from ..catalog import RED_LINES
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
        }

    def _factcheck(self, *a):
        return {"status": "supported", "reason": "fake",
                "sources": [{"url": "https://example.org/fake-source",
                             "supporting_excerpt": "fake excerpt"}]}

    def _context(self, *a):
        return {"findings": [{"summary": "fake news item", "url": "https://example.org/fake-source",
                              "date": "2026-10-01", "relevance": "low"}]}

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

    def _plan_a(self, *a):
        return {"paragraphs": [], "corrections": []}

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
                "monitoring_keywords": ["fake"],
                "escalation": [{"trigger": "media call", "action": "route to PR lead",
                                "owner": "PR lead"}], "do_not_say": ["no comment"]}

    def _rereview(self, model, ids, paras, bias, prompt, schema):
        found = sorted(set(re.findall(r'"id": "(R\d+)"', prompt)))
        return {"verdicts": [{"issue": f, "verdict": "FULLY", "note": "fake"} for f in found]}
