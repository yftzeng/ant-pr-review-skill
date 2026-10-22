import json
import re

from ant_pr_review.jmerge import run_jmerge
from ant_pr_review.jsonio import read_json
from ant_pr_review.refresh import compute_synthesis
from ant_pr_review.report import write_report
from ant_pr_review.review import run_round1
from ant_pr_review.store import DEFAULT_THRESHOLDS
from helpers import M1, M2, ScriptBackend, auto_review, make_run, risk

Q = lambda *_: None


def compare(prompt):
    js = sorted(set(re.findall(r'"(tw|us)": \{', prompt)))
    return {"differences": [{"topic": "disclosure", "by_jurisdiction": [
        {"jurisdiction": j, "position": f"pos-{j}"} for j in js]}],
        "questions": [{"id": f"Q{n}", "jurisdiction": j, "question": f"question for {j}?"}
                      for n, j in enumerate(js, 1)]}


FINAL = {"summary": "tw is no-go per the merger", "common_risks": ["quote out of context"],
         "differences": [{"topic": "disclosure", "by_jurisdiction": [
             {"jurisdiction": "tw", "position": "stricter"},
             {"jurisdiction": "us", "position": "FTC guides"}]}],
         "strictest": "tw", "notes": [{"jurisdiction": "tw", "note": "no-go"},
                                      {"jurisdiction": "us", "note": "ok"}]}


def discuss(prompt):
    qs = re.findall(r'"id": "(Q\d+)"', prompt.split("Your panel's results")[0])
    return {"answers": [{"question": q, "answer": "a", "revised": False, "revision": ""}
                        for q in qs]}


def reviewed(tmp_path, js=("tw", "us")):
    run = make_run(tmp_path, jurisdictions=js, depth="quick")
    run_round1(run, ScriptBackend({(M1, "review"): auto_review(risks=[risk(likelihood=3,
                                                                             impact=3)]),
                                   (M2, "review"): auto_review()}), [M1, M2], "en", say=Q)
    compute_synthesis(run, [M1, M2], DEFAULT_THRESHOLDS)
    return run


def merge_backend():
    return ScriptBackend({(M1, "jcompare"): compare, ("*", "jdiscuss"): discuss,
                          (M1, "jfinal"): FINAL})


# @S-jurisdiction-merge-001
def test_single_jurisdiction_needs_no_merger(tmp_path):
    run = reviewed(tmp_path, js=("tw",))
    b = merge_backend()
    assert run_jmerge(run, b, M1, "en", say=Q) is None and b.calls == []
    meta = write_report(run, read_json(run.path("06-synthesis.json")), lang="en")
    assert meta["files"] == ["08-report.v1.md"]


# @S-jurisdiction-merge-002 @N-jurisdiction-merge-001
def test_compare_then_per_jurisdiction_discussion_then_final(tmp_path):
    run = reviewed(tmp_path)
    b = merge_backend()
    run_jmerge(run, b, M1, "en", say=Q)
    tasks = [c["task"] for c in b.calls]
    assert tasks[0] == "jcompare" and tasks[-1] == "jfinal"
    disc = [c for c in b.calls if c["task"] == "jdiscuss"]
    assert sorted((c["model"], "jurisdiction tw" in c["system"]) for c in disc) == [
        (M1, False), (M1, True), (M2, False), (M2, True)]
    for c in disc:
        j = "tw" if "jurisdiction tw" in c["system"] else "us"
        other = "us" if j == "tw" else "tw"
        asked = c["prompt"].split("Your panel's results")[0]
        assert f"question for {j}?" in asked and f"question for {other}?" not in asked
    # round 1 never mixed two jurisdictions in one call
    syn = read_json(run.path("06-synthesis.json"))
    assert {u: v["scope"] for u, v in syn["units"].items()} == {
        "global.all": "global", "tw.all": "tw", "us.all": "us"}


# @S-jurisdiction-merge-003
def test_consolidated_and_per_jurisdiction_reports(tmp_path):
    run = reviewed(tmp_path)
    run_jmerge(run, merge_backend(), M1, "en", say=Q)
    meta = write_report(run, read_json(run.path("06-synthesis.json")), lang="en")
    assert meta["files"] == ["08-report.v1.md", "08-report.v1.tw.md", "08-report.v1.us.md"]
    md = run.path("08-report.v1.md").read_text()
    assert "Jurisdiction comparison" in md and "FTC guides" in md
    assert "08-report.v1.tw.md" in md and "08-report.v1.us.md" in md
    tw = run.path("08-report.v1.tw.md").read_text()
    assert "· Taiwan (v1)" in tw and "Jurisdiction comparison" not in tw


# @S-jurisdiction-merge-004
def test_merger_text_never_changes_a_verdict(tmp_path):
    run = reviewed(tmp_path)
    before = read_json(run.path("06-synthesis.json"))["jurisdictions"]["tw"]["verdict"]
    run_jmerge(run, merge_backend(), M1, "en", say=Q)
    meta = write_report(run, read_json(run.path("06-synthesis.json")), lang="en")
    assert before == "conditional" and meta["verdicts"]["tw"] == "conditional"


# @S-jurisdiction-merge-005
def test_resumed_merge_skips_done_discussions(tmp_path):
    run = reviewed(tmp_path)
    run_jmerge(run, merge_backend(), M1, "en", say=Q)
    for p in run.path("07-jmerge/discuss/us").glob("*.json"):
        p.unlink()
    b = merge_backend()
    run_jmerge(run, b, M1, "en", say=Q)
    assert [c["task"] for c in b.calls] == ["jdiscuss", "jdiscuss", "jfinal"]
    assert all("jurisdiction us" in c["system"] for c in b.calls if c["task"] == "jdiscuss")
    assert json.loads(run.path("07-jmerge/final.json").read_text())["status"] == "ok"
