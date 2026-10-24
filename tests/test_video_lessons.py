"""Adopted from three brake-pedal crisis commentary videos (docs/REFERENCES.md #24)."""
import re
from pathlib import Path

from ant_pr_review import drafting
from ant_pr_review.catalog import item_index

ROOT = Path(__file__).resolve().parents[1]


# @S-checklist-019
def test_items_and_amendments():
    idx = item_index()
    assert "admission" in idx["JOU-16"]["text"] and "upgrade" in idx["JOU-16"]["text"]
    assert "Fast actions, slow conclusions" in idx["JOU-17"]["text"]
    assert "replicate" in idx["JOU-17"]["text"]
    assert "commissioned" in idx["JOU-18"]["text"] and "one voice" in idx["JOU-18"]["text"]
    assert "third party" in idx["JOU-09"]["text"] and "safety is at stake" in idx["JOU-09"]["text"]
    assert "off the record" in idx["STK-01"]["text"]
    refs = (ROOT / "docs" / "REFERENCES.md").read_text()
    sec = refs.split("## 24.", 1)[1]
    for bv in ("BV19bpg6kEWr", "BV1hMpE6FEXG", "BV1dmJi6yEAi"):
        assert bv in sec, bv
    assert not re.search(r"讲述者|讲书者|講述者", sec)


# @S-drafting-016
def test_brake_pedal_counter_examples():
    ex = drafting.examples_for("rebut")
    new = [e for e in ex if e["org"] == "某汽車品牌"]
    assert len(new) == 2 and all(e["kind"] == "counter" and e["verified"] is False for e in new)
    lessons = " ".join(e["lesson"] for e in new)
    assert "upgrade" in lessons and "commissioned" in lessons
    block = drafting.examples_block(ex)
    assert block.count("某汽車品牌") == 2


# @S-checklist-020
def test_unsent_statement_sharpens_three_items():
    idx = item_index()
    assert "whether or not" in idx["JOU-17"]["text"] and "cooperat" in idx["JOU-17"]["text"]
    j6 = idx["JOU-06"]["text"]
    assert "no reports" in j6 and "channel" in j6 and "not proof of no defect" in j6
    assert "starting point" in idx["SOC-10"]["text"]
    sec = (ROOT / "docs" / "REFERENCES.md").read_text().split("## 24.", 1)[1]
    assert "BV1hMpE6FEXG at 24:17" in sec
    for phrase in ("不放過", "安全沒有終點", "第一時間", "高度重視"):
        assert phrase not in sec, phrase


# @S-drafting-023
def test_w10_intensifier_without_a_figure():
    from test_drafting_bounds import para, version
    v = version(paras=[para("我們已第一時間全面覆核。", "measures"),
                       para("我們已於 10 月 21 日 14:00 開始覆核。", "measures"),
                       para("We acted immediately.", "measures"),
                       para("這份報告的全面性仍待確認。", "facts")])
    hits = [h for h in drafting.w_checks(v, "promote") if h["id"] == "W10"]
    assert [h["where"] for h in hits] == ["P1", "P1", "P3"]
    assert {h["hit"] for h in hits} == {"第一時間", "全面覆核", "immediately"}
    timed = version(paras=[para("我們已於 10 月 21 日 14:00 第一時間封存 32 輛車。", "measures")])
    assert not [h for h in drafting.w_checks(timed, "promote") if h["id"] == "W10"]
    from ant_pr_review.i18n import T
    en, tw, cn = (T(lang)("draft.w.W10") for lang in ("en", "zh-TW", "zh-CN"))
    assert en != "draft.w.W10" and len({en, tw, cn}) == 3  # each locale has its own text


# @S-drafting-024
def test_writer_scopes_absence_and_never_reframes_the_crisis():
    from ant_pr_review import prompts
    s = prompts.draft_system("en", {"posture": "rebut", "means": ["white"]}, tier4=False)
    for needle in ("names its basis", "never reads as 'no defect'",
                   "whether or not the other side cooperates", "starting point"):
        assert needle in s, needle
