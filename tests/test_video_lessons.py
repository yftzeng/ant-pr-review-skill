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
