"""JSON Schemas for every model step, plus a small validator (subset of draft 2020-12).

The validator covers what the schemas here use: type, properties, required,
additionalProperties=false, items, enum, minimum/maximum.
"""
from __future__ import annotations

from typing import Any

_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "integer": int, "number": (int, float), "null": type(None),
}


def validate(value: Any, schema: dict, path: str = "$") -> list[str]:
    errs: list[str] = []
    typ = schema.get("type")
    if typ:
        types = typ if isinstance(typ, list) else [typ]
        ok = False
        for t in types:
            py = _TYPES[t]
            if isinstance(value, bool) and t in ("integer", "number"):
                continue
            if isinstance(value, py):
                ok = True
                break
        if not ok:
            return [f"{path}: expected {typ}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in {schema['enum']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append(f"{path}: {value} < {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errs.append(f"{path}: {value} > {schema['maximum']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{path}: missing '{k}'")
        if schema.get("additionalProperties") is False:
            for k in value:
                if k not in props:
                    errs.append(f"{path}: unexpected '{k}'")
        for k, sub in props.items():
            if k in value:
                errs.extend(validate(value[k], sub, f"{path}.{k}"))
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errs.extend(validate(item, schema["items"], f"{path}[{i}]"))
    return errs


def obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props,
            "required": list(props) if required is None else required,
            "additionalProperties": False}


def arr(items: dict) -> dict:
    return {"type": "array", "items": items}


STR = {"type": "string"}
INT = {"type": "integer"}  # 0-5; clamped in code (structured outputs ignore min/max)
BOOL = {"type": "boolean"}


def enum(values: list[str]) -> dict:
    return {"type": "string", "enum": list(values)}


CLAIM_TYPES = ["date", "number", "law", "proper_noun", "quote", "allegation", "legal_citation",
               "other"]
FACT_STATUS = ["supported", "partly", "unsupported", "cannot_verify"]
RL_SEVERITY = ["none", "low", "medium", "high"]


def review_schema() -> dict:
    from .catalog import DIMENSIONS, RED_LINES, VERDICTS, all_party_types
    risk = obj({
        "id": STR,                   # reviewer-local, e.g. "R3"
        "anchor": STR,               # "D1.P03.S2" or "absence: <where> - expected <item>; checked: ..."
        "item": STR,                 # checklist id it answers, or ""
        "dimension": enum(DIMENSIONS),
        "scenario": STR,             # trigger -> spread -> consequence
        "standard": STR,             # the law, rule or expectation at stake
        "why_it_matters": STR,
        "mitigation": STR,
        "likelihood": INT,
        "impact": INT,
        "legal_refs": arr(STR),
        "claim_ids": arr(STR),
    })
    return obj({
        "orientation": STR,
        "checklist": arr(obj({"item": STR, "verdict": enum(VERDICTS), "likelihood": INT,
                              "impact": INT, "anchors": arr(STR), "evidence": STR})),
        "risks": arr(risk),
        "claims": arr(obj({"id": STR, "anchor": STR, "text": STR, "type": enum(CLAIM_TYPES)})),
        "red_lines": arr(obj({"key": enum(RED_LINES), "flag": BOOL, "severity": enum(RL_SEVERITY),
                              "anchors": arr(STR), "comment": STR})),
        "worst_headlines": arr(STR),
        # D-0003: every party type in a stakeholders unit, [] elsewhere
        "stakeholders": arr(obj({"type": enum(all_party_types()),
                                 "relevance": enum(["none", "low", "high"]), "reaction": STR,
                                 "needs": STR, "handling": STR, "likelihood": INT,
                                 "impact": INT})),
    })


FACTCHECK = obj({
    "status": enum(FACT_STATUS),
    "reason": STR,
    "sources": arr(obj({"url": STR, "supporting_excerpt": STR})),
})

DEBATE = obj({
    "responses": arr(obj({
        "target": STR,               # "<model>:R1", "<model>:redline:<key>", "<model>:item:<ID>"
        "position": enum(["corroborate", "dispute"]),
        "evidence": STR,
        "duplicate_of": STR,         # own risk id if it is the same finding, else ""
    })),
})

_BY_J = arr(obj({"jurisdiction": STR, "position": STR}))

JCOMPARE = obj({
    "differences": arr(obj({"topic": STR, "by_jurisdiction": _BY_J})),
    "questions": arr(obj({"id": STR, "jurisdiction": STR, "question": STR})),
})

JDISCUSS = obj({
    "answers": arr(obj({"question": STR, "answer": STR, "revised": BOOL, "revision": STR})),
})

JFINAL = obj({
    "summary": STR,
    "common_risks": arr(STR),
    "differences": arr(obj({"topic": STR, "by_jurisdiction": _BY_J})),
    "strictest": STR,
    "notes": arr(obj({"jurisdiction": STR, "note": STR})),
})

PLAN_A = obj({
    "paragraphs": arr(obj({"id": STR, "text": STR})),
    "corrections": arr(obj({"from": STR, "to": STR, "category": STR})),
})

PLAN_B = obj({
    "recommendation": enum(["publish_revised", "do_not_publish"]),
    "headline_options": arr(STR),
    "paragraphs": arr(obj({"id": STR, "text": STR, "addresses": arr(STR)})),
    "alternative": STR,
    "notes": STR,
})

# operation direction: there is deliberately no field for an "improved" operation (D-PR-7).
PLAN_B_OPERATION = obj({
    "recommendation": enum(["do_not_proceed", "transparent_alternative"]),
    "alternative_plan": STR,
    "rationale": STR,
    "addresses": arr(STR),
})

RESPONSE_OPTIONS = obj({
    "options": arr(obj({"option": enum(["silence", "clarify", "correct", "legal",
                                        "platform_notice"]),
                        "when": STR, "risks": STR, "addresses": arr(STR)})),
    "recommended": STR,
    "statement_draft": STR,
})

KEYWORD_KINDS = ["brand", "variant", "product", "officer", "issue", "competitor", "exclusion"]
RELEVANCE = ["none", "low", "high"]

KIT = obj({
    "holding_statement": STR,
    "formal_statement": STR,
    "qa": arr(obj({"question": STR, "answer": STR})),
    "monitoring_keywords": arr(obj({"term": STR, "kind": enum(KEYWORD_KINDS),
                                     "platforms": arr(STR)})),
    "escalation": arr(obj({"trigger": STR, "action": STR, "owner": STR})),
    "do_not_say": arr(STR),
})

REREVIEW = obj({
    "verdicts": arr(obj({
        "issue": STR,
        "verdict": enum(["FULLY", "PARTIALLY", "NOT_ADDRESSED", "MADE_WORSE"]),
        "note": STR,
    })),
})

ATTENTION_STAGES = ["pre_problem", "alarmed", "cost", "decline", "post_problem"]  # Downs
AUDIENCES = ["affected", "staff", "partners", "investors", "regulators", "exchange", "press",
             "public"]

# D-0002: the timeline of means and its independent labelling. `day` is relative to the
# publish day (T0); `time` is HH:MM local to the first jurisdiction.
TIMELINE = obj({
    "steps": arr(obj({"day": {"type": "integer"}, "time": STR, "action": STR,
                      "category": enum(["white", "gray", "black"]), "channel": STR, "notes": STR,
                      "trigger": STR, "stop": STR, "audience": enum(AUDIENCES),
                      "paid": BOOL, "promotional": BOOL, "poll": BOOL,
                      "stage": enum(ATTENTION_STAGES), "silence": BOOL})),
    "excluded": arr(obj({"tactic": STR, "why": STR, "law": STR, "exposure": STR, "watch_for": STR,
                         "lawful_alternative": STR})),
})

CLASSIFY_MEANS = obj({
    "labels": arr(obj({"step": {"type": "integer"}, "category": enum(["white", "gray", "black"]),
                       "reason": STR})),
    "excluded_flags": arr(obj({"entry": {"type": "integer"}, "problem": STR})),
})

# D-0004: competitors with the evidence the search returned
PROFILE_SEARCH = obj({
    "competitors": arr(obj({
        "name": STR, "role": enum(["direct", "indirect", "substitute", "benchmark"]),
        "evidence": arr(obj({"url": STR,
                             "kind": enum(["registry", "regulator", "exchange_filing",
                                           "independent", "company_claim", "aggregator",
                                           "lead"]),
                             "excerpt": STR})),
    })),
})

CONTEXT_SEARCH = obj({
    "findings": arr(obj({"summary": STR, "url": STR, "date": STR,
                         "relevance": enum(["high", "medium", "low"])})),
})

# D-0005: drafting. Two versions with their parts, the lead's 5W1H and the claim register.
DRAFT = obj({
    "versions": arr(obj({
        "approach": STR, "title": STR,
        "paragraphs": arr(obj({"text": STR,
                               "part": enum(["stance", "facts", "cause", "measures", "other"])})),
        "lead_5w1h": obj({"who": STR, "what": STR, "when": STR, "where": STR, "why": STR,
                          "how": STR}),
        "claims": arr(obj({"text": STR, "basis": arr(STR),
                           "class": enum(["public", "internal", "not_supportable",
                                          "needs_validation"])})),
    })),
    "blocking_questions": arr(STR),
    "contradictions": arr(STR),
})

DRAFT_REVIEW = obj({
    "versions": arr(obj({"version": STR, "issues": arr(obj({
        "kind": enum(["unsupported_fact", "contradiction", "missing_part", "status_overstated",
                      "early_conclusion", "commitment_crossed", "tone", "other"]),
        "text": STR}))})),
})

DRAFT_REASON = obj({"reason": STR})
