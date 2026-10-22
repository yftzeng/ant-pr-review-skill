"""Adopted from the user's own reference notes (docs/REFERENCES.md #23, local only)."""
from pathlib import Path

from ant_pr_review import prompts
from ant_pr_review.catalog import item_index
from ant_pr_review.i18n import T

ROOT = Path(__file__).resolve().parents[1]


# @S-checklist-018
def test_items_and_amendments():
    idx = item_index()
    assert "never suggest a bridge" in idx["JOU-15"]["text"]
    assert "decision not to prosecute" in idx["LEG-14"]["text"]
    assert "staff IDs" in idx["INT-08"]["text"]
    assert "caused a misunderstanding" in idx["APO-01"]["text"]
    assert "patents" in idx["SOC-10"]["text"]
    assert "arranged" in idx["JOU-06"]["text"]
    assert "injured or died" in idx["SOC-07"]["text"]
    assert "own stake" in idx["LEG-03"]["text"]
    refs = (ROOT / "docs" / "REFERENCES.md").read_text()
    assert "## 23." in refs and "never committed" in refs


# @S-plans-037
def test_kit_prompt_q_and_a_rules():
    s = prompts.kit_system("en")
    for needle in ("restates the question", "who is checking", "names the reason",
                   "harm to people", "no pivot", "'no comment' without a reason"):
        assert needle in s, needle


# @S-review-matrix-030
def test_disclaimer_in_three_languages():
    assert "communication risk only" in T("en")("report.disclaimer")
    assert "makes no tactic acceptable" in T("en")("report.disclaimer")
    assert "僅評估傳播風險" in T("zh-TW")("report.disclaimer")
    assert "仅评估传播风险" in T("zh-CN")("report.disclaimer")
