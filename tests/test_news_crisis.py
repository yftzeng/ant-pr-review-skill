"""Items borrowed from med-political, med-news-reporter, ziyu, crisis-pr-response (#19-22)."""
from pathlib import Path

from ant_pr_review.catalog import item_index, pack, party_info
from ant_pr_review.i18n import T
from ant_pr_review.timeline import build

ROOT = Path(__file__).resolve().parents[1]


# @S-checklist-017
def test_items_packs_parties_and_credits():
    idx = item_index()
    new = ("EXP-05", "LEG-12", "LEG-13", "JOU-13", "JOU-14", "POL-04", "INT-07", "RSP-06",
           "SOC-11")
    for i in new:
        assert i in idx, i
    refs = {law["ref"] for law in pack("tw")["law"]}
    for needle in ("Anti-Infiltration", "Political Donations", "art. 73", "art. 245"):
        assert any(needle in r for r in refs), needle
    assert any(b.get("kind") == "poll" for b in pack("tw").get("blackout", []))
    assert any("Maimai" in p for p in pack("cn")["platforms"])
    assert "franchisees" in party_info("channel")["text"]
    text = (ROOT / "docs" / "REFERENCES.md").read_text()
    for i in new:
        assert i in text, i
    for sha in ("fa893b32eb2148cb41a09dcfd9255c9ac13ae70e",
                "9fabde2f3d4630be5693d582fb138a8bddd07536"):
        assert sha in text
    assert "docs/references/" in (ROOT / ".gitignore").read_text()


# @S-plans-036
def test_poll_step_in_the_blackout_is_dropped():
    raw = [{"day": d, "time": "10:00", "action": a, "category": "white", "channel": "",
            "notes": "", "trigger": "", "stop": "", "audience": "public", "paid": False,
            "promotional": False, "poll": True} for a, d in (("Publish our poll", 5),
                                                             ("Early poll note", 1))]
    labels = {1: {"category": "white", "reason": ""}, 2: {"category": "white", "reason": ""}}
    out = build(raw, labels, [], {}, ["white", "gray"], "2026-11-15", ["tw"], "w", t=T("en"),
                posture="promote")
    assert [s["action"] for s in out["steps"]] == ["Early poll note"]
    assert [(d["action"], d["reason"]) for d in out["dropped"]] == [
        ("Publish our poll", "poll_blackout")]
