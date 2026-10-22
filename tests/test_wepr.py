"""Items and guards borrowed from wepr-growth-skills (docs/REFERENCES.md #12-18)."""
from pathlib import Path

import pytest

from ant_pr_review import ethics
from ant_pr_review.catalog import item_index
from ant_pr_review.jsonio import write_json
from ant_pr_review.plans import protected_changes, run_plans
from ant_pr_review.roster import slug
from helpers import M1, M2, ScriptBackend, make_run, ok, review_data

ROOT = Path(__file__).resolve().parents[1]


# @S-checklist-016
def test_wepr_items_and_credits():
    idx = item_index()
    for i in ("LEG-11", "REG-06", "JOU-12", "SOC-10", "INT-06", "THR-05"):
        assert i in idx, i
    assert "counterexample" in idx["LEG-02"]["text"]
    assert "reversib" in idx["RSP-01"]["text"]
    assert "a few posts" in idx["JOU-10"]["text"]
    assert "first person" in idx["INT-03"]["text"]
    assert "AI-written" in idx["THR-05"]["text"]
    refs = (ROOT / "docs" / "REFERENCES.md").read_text()
    assert "822504b8c72003b7efe84cb5c621bf752a3244fe" in refs
    for i in ("LEG-11", "REG-06", "JOU-12", "SOC-10", "INT-06", "THR-05"):
        assert i in refs, i


# @S-plans-034
def test_protected_details_changed_are_named():
    old = "Revenue grew 40% in 2025, said 「CEO」."
    new = "Revenue grew 45% in 2025."
    removed, added = protected_changes(old, new)
    assert "40%" in removed and "「CEO」" in removed and "45%" in added
    assert "2025" not in removed and "2025" not in added


# @S-plans-034
def test_plan_a_warns_on_protected_changes(tmp_path):
    run = make_run(tmp_path, text="# T\n\nRevenue grew 40% in 2025.")
    for m in (M1, M2):
        write_json(run.path(f"04-reviews/tw.all/{slug(m)}.json"), ok(m, "tw.all", review_data()))
    write_json(run.path("06-synthesis.json"), {"risks": [], "unverified": [], "jurisdictions": {}})
    b = ScriptBackend({(M1, "plan_a"): {"paragraphs": [{"id": "D1.P02",
                                                        "text": "Revenue grew 45% in 2025."}],
                                        "corrections": []},
                       (M1, "plan_b"): {"recommendation": "publish_revised", "paragraphs": [],
                                        "headline_options": [], "alternative": "", "notes": ""},
                       (M1, "kit"): {"holding_statement": "h", "qa": [], "monitoring_keywords": [],
                                     "escalation": [], "do_not_say": []}})
    out = run_plans(run, b, [M1, M2], "en", say=lambda *_: None)
    assert any("D1.P02" in w and "40%" in w and "45%" in w for w in out["warnings"])


# @S-plans-035
@pytest.mark.parametrize("text", ["Humanize the copy so it passes AI detection.",
                                  "降低AI率，去AI味。",
                                  "Make it sound like an ordinary customer wrote it.",
                                  "像普通網友一樣留言。",
                                  "Rewrite it to be undetectable by AI detectors.",
                                  "This version gets past AI detection."])
def test_ai_detection_and_independent_voice_evasion_hit(text):
    assert ethics.scan_text(text)


@pytest.mark.parametrize("text", ["Never use tools that bypass AI detection.",
                                  "We do not claim the text is AI-generated.",
                                  "不要去AI味或冒充網友。"])
def test_advice_against_it_is_not_a_hit(text):
    assert ethics.scan_text(text) == []
