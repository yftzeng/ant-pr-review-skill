"""The second set of borrowed items and timeline rules (D-0003, docs/REFERENCES.md #7-11)."""
from pathlib import Path

import pytest

from ant_pr_review.catalog import item_index
from ant_pr_review.i18n import T
from ant_pr_review.timeline import build

t = T("en")
ROOT = Path(__file__).resolve().parents[1]


# @S-checklist-015
def test_borrowed_items_and_credits():
    idx = item_index()
    for i in ("JOU-10", "JOU-11", "INT-05", "REG-05", "RSP-05", "SOC-09"):
        assert i in idx, i
    assert "temporary worker" in idx["JOU-06"]["text"]
    assert "will not happen again" in idx["JOU-06"]["text"]
    refs = (ROOT / "docs" / "REFERENCES.md").read_text()
    for i in ("JOU-10", "JOU-11", "INT-05", "REG-05", "RSP-05", "SOC-09"):
        assert i in refs, i
    for sha in ("eeed137fb9cb792432dc67f84b443c69c58fa0af",
                "c4db8ffb9afbbdbe125a1ff91ad2312ceb863189",
                "a4ea626a81fc90e41072e13f833e0ae6f8da8152",
                "349f34486ca3ce3d80ccc5ab6f81259b748664b0",
                "39e119bfef25957223d6c44fccab0329e936d2f6"):
        assert sha in refs
    from ant_pr_review.catalog import pack
    assert any("快手" in p for p in pack("cn")["platforms"])


def _steps(*rows):
    raw = [{"day": d, "time": tm, "action": a, "category": "white", "channel": "", "notes": "",
            "trigger": "", "stop": "", "audience": aud, "paid": False,
            "promotional": promo} for a, aud, d, tm, promo in rows]
    return raw, {n: {"category": "white", "reason": ""} for n in range(1, len(raw) + 1)}


def _warned(out, word):
    return [s["action"] for s in out["steps"] if any(word in w for w in s["warnings"])]


# @S-plans-031
@pytest.mark.parametrize("posture,expected", [("clarify_apologize", ["Launch promo"]),
                                              ("promote", [])])
def test_no_promotion_before_the_affected_are_helped(posture, expected):
    raw, labels = _steps(("Launch promo", "public", 0, "09:00", True),
                         ("Tell customers", "affected", 0, "10:00", False))
    out = build(raw, labels, [], {}, ["white", "gray"], "", ["tw"], "w", t=t, posture=posture)
    assert _warned(out, "promotion") == expected


# @S-plans-032
def test_the_exchange_hears_first():
    raw, labels = _steps(("Press release", "press", 0, "09:00", False),
                         ("Exchange filing", "exchange", 0, "16:00", False))
    out = build(raw, labels, [], {}, ["white", "gray"], "", ["tw"], "w", t=t, posture="promote")
    assert _warned(out, "filing") == ["Press release"]


# @S-plans-033
def test_public_step_while_claims_are_unverified():
    raw, labels = _steps(("Owned page", "staff", 0, "08:00", False),
                         ("Press release", "press", 0, "09:00", False),
                         ("Post", "public", 1, "09:00", False))
    out = build(raw, labels, [], {}, ["white", "gray"], "", ["tw"], "w", t=t, posture="promote",
                unverified=["K2", "K5"])
    assert _warned(out, "unverified") == ["Press release"]
    assert any("K2" in w and "K5" in w for w in out["steps"][1]["warnings"])
    out = build(raw, labels, [], {}, ["white", "gray"], "", ["tw"], "w", t=t, posture="promote")
    assert _warned(out, "unverified") == []


# @S-review-matrix-028
def test_reaction_column_is_labelled_simulated():
    assert "model-simulated" in t("report.reaction")


# @S-plans-031
def test_promotion_without_an_affected_step_or_on_a_tie_warns():
    raw, labels = _steps(("Launch promo", "public", 0, "09:00", True))
    out = build(raw, labels, [], {}, ["white", "gray"], "", ["tw"], "w", t=t,
                posture="clarify_apologize")
    assert _warned(out, "promotion") == ["Launch promo"]
    raw, labels = _steps(("Launch promo", "public", 0, "09:00", True),
                         ("Tell customers", "affected", 0, "09:00", False))
    out = build(raw, labels, [], {}, ["white", "gray"], "", ["tw"], "w", t=t, posture="rebut")
    assert _warned(out, "promotion") == ["Launch promo"]


# @S-plans-033
def test_unverified_ledger_claims_reach_the_timeline(tmp_path):
    from ant_pr_review.factcheck import write_ledger
    from ant_pr_review.jsonio import read_json, write_json
    from ant_pr_review.plans import run_plans
    from ant_pr_review.roster import slug
    from helpers import M1, M2, ScriptBackend, make_run, ok, review_data
    run = make_run(tmp_path, text="# T\n\nRevenue grew 40%.")
    for m in (M1, M2):
        write_json(run.path(f"04-reviews/tw.all/{slug(m)}.json"), ok(m, "tw.all", review_data()))
    write_json(run.path("06-synthesis.json"), {"risks": [], "unverified": [], "jurisdictions": {}})
    write_ledger(run, [{"id": "K7", "anchor": "D1.P02.S1", "text": "Revenue grew 40%",
                        "type": "number", "status": "cannot_verify", "reason": "no_source",
                        "refs": [], "sources": []},
                       {"id": "K8", "anchor": "D1.P02.S1", "text": "x", "type": "number",
                        "status": "supported", "refs": [], "sources": []}])
    step = {"day": 0, "time": "09:00", "action": "Press release", "category": "white",
            "channel": "", "notes": "", "trigger": "", "stop": "", "audience": "press",
            "paid": False, "promotional": False}
    b = ScriptBackend({(M1, "timeline"): {"steps": [step], "excluded": []},
                       (M2, "classify_means"): {"labels": [{"step": 1, "category": "white",
                                                            "reason": ""}], "excluded_flags": []},
                       (M1, "plan_a"): {"paragraphs": [], "corrections": []},
                       (M1, "plan_b"): {"recommendation": "publish_revised", "paragraphs": [],
                                        "headline_options": [], "alternative": "", "notes": ""},
                       (M1, "kit"): {"holding_statement": "h", "qa": [], "monitoring_keywords": [],
                                     "escalation": [], "do_not_say": []}})
    run_plans(run, b, [M1, M2], "en", say=lambda *_: None)
    w = read_json(run.path("09-plans/T.json"))["steps"][0]["warnings"]
    assert any("K7" in x for x in w) and not any("K8" in x for x in w)
