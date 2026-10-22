"""Drafting mode: a fixed brief, two versions audited by the same matrix, ranked in code
(D-0005)."""
import json
import re
from pathlib import Path

import pytest

from ant_pr_review import drafting
from ant_pr_review.backends.base import BackendError, Result
from ant_pr_review.i18n import T
from ant_pr_review.intake import build_intake_from_args, purpose_of, run_intake_interactive
from ant_pr_review.jsonio import read_json, write_json
from ant_pr_review.review import load_records
from ant_pr_review.store import DEFAULT_THRESHOLDS
from ant_pr_review.ui import ScriptedIO
from helpers import M1, M2, ScriptBackend, auto_review, make_run

t = T("en")

BRIEF = {"kind": "product", "confirmed": ["A batch of 1,200 units shipped with a faulty seal"],
         "alleged": ["The fault caused burns"], "unknown": ["How many units are still in use"],
         "affected": "buyers of the March batch", "emotion": "fear",
         "outcome": "buyers stop using the units and get a replacement",
         "decision": "publish", "prior": [], "actions_done": ["Sales of the batch stopped"],
         "actions_in_progress": ["Testing returned units"], "actions_planned": ["A recall"],
         "approvers": ["legal", "CEO office"], "tier4": []}


def para(text, part="facts"):
    return {"text": text, "part": part}


def version(approach="apology first", paras=None, claims=None, w=None, title="Our statement"):
    return {"approach": approach, "title": title,
            "paragraphs": paras if paras is not None else [
                para("We are sorry: the seal on 1,200 units from March may fail.", "stance"),
                para("On 20 October we found the seal fault in the March batch.", "facts"),
                para("The cause is a supplier part; testing continues.", "cause"),
                para("Stop using the unit; we replace it free from 1 November.", "measures")],
            "lead_5w1h": w or {"who": "we", "what": "seal fault", "when": "20 October",
                               "where": "March batch", "why": "supplier part",
                               "how": "replacement"},
            "claims": claims if claims is not None else [
                {"text": "the seal on 1,200 units from March may fail", "basis": ["C1"],
                 "class": "public"}]}


V2_PARAS = [para("Buyers of the March batch: please stop using the unit today.", "stance"),
            para("A seal fault affects 1,200 units, found on 20 October.", "facts"),
            para("A supplier part is the likely cause; tests run until 30 October.", "cause"),
            para("Free replacements start on 1 November at every store.", "measures")]


def writer_answer(v1=None, v2=None, questions=(), contradictions=()):
    return {"versions": [v1 or version(), v2 or version("action first", V2_PARAS)],
            "blocking_questions": list(questions), "contradictions": list(contradictions)}


def drafting_run(tmp_path, brief=None, posture="clarify_apologize", models=(M1, M2)):
    run = make_run(tmp_path, models=models)
    intake = build_intake_from_args("outbound", [], lang="en", posture=posture,
                                    purpose="drafting", brief=brief or BRIEF)
    write_json(run.path("00-intake.json"), intake)
    m = read_json(run.path("03-matrix.json"))
    m["units"] = m["units"][:2]
    write_json(run.path("03-matrix.json"), m)
    return run


def backend(writer=None, review=None, reason=None, verdicts=None):
    return ScriptBackend({("*", "draft"): writer or writer_answer(),
                          ("*", "draft_review"): review or {"versions": [
                              {"version": "V1", "issues": []},
                              {"version": "V2", "issues": [{"kind": "tone", "text": "stiff"}]}]},
                          ("*", "draft_reason"): reason or {
                              "reason": "V1 passes 100% of items with top score 0."},
                          ("*", "review"): auto_review(verdicts)})


def draft(run, b, interactive=False, answers=()):
    io = ScriptedIO(list(answers))
    return drafting.run_draft(run, b, [M1, M2], "en", DEFAULT_THRESHOLDS, io=io,
                              interactive=interactive, say=lambda *a: None), io


# @S-drafting-001
def test_purpose_first_and_drafting_asks_the_brief():
    # purpose: drafting (2); role, identity, posture, means: defaults
    answers = ["2", "", "", "", "",
               "1",                                   # kind: the first
               "A batch shipped with a faulty seal", "/done",   # confirmed
               "/done", "How many units are in use", "/done",     # alleged, unknown
               "buyers of the March batch", "2",       # affected, emotion: the second
               "buyers get a replacement", "",         # outcome, decision: default
               "/done", "Sales stopped", "/done", "/done", "/done",  # prior, actions
               "legal", "", "/done",                   # approvers, characterised: no, cannot commit
               "",                                     # tier-4 flags: none
               "/done"]                                # material: none
    from test_context_card import FILL
    io = ScriptedIO(answers + FILL + [""])
    intake = run_intake_interactive(io, t, "en")
    assert intake["purpose"] == "drafting" and intake["direction"] == "outbound"
    assert "What are we reviewing?" not in io.text
    b = intake["brief"]
    assert [f["id"] for f in b["facts"]] == ["C1", "U1"] and b["decision"] == "publish"
    assert b["actions"] == [{"text": "Sales stopped", "status": "done"}]
    assert intake["targets"] == [] and intake["materials"] == []
    # Enter keeps audit, and an audit asks the direction and the targets as before
    io = ScriptedIO(["", "", "", "", "", "", "Some text", "/done"] + FILL + [""])
    intake = run_intake_interactive(io, t, "en")
    assert intake["purpose"] == "audit" and "brief" not in intake
    assert "What are we reviewing?" in io.text and intake["targets"][0]["value"] == "Some text"
    assert purpose_of({"direction": "outbound"}) == "audit"


# @S-drafting-002
def test_brief_file_is_validated():
    intake = build_intake_from_args("outbound", ["notes.txt"], lang="en", purpose="drafting",
                                    brief=BRIEF)
    facts = intake["brief"]["facts"]
    assert [(f["id"], f["status"]) for f in facts] == [("C1", "confirmed"), ("A1", "alleged"),
                                                       ("U1", "unknown")]
    assert intake["targets"] == [] and intake["materials"][0]["value"] == "notes.txt"
    for bad, word in ((dict(BRIEF, confirmed=[], alleged=[]), "confirmed or alleged"),
                      (dict(BRIEF, kind="war"), "product"),
                      (dict(BRIEF, decision="ignore"), "monitor"),
                      (dict(BRIEF, emotion="joyful"), "anger"),
                      (dict(BRIEF, tier4=["aliens"]), "injury")):
        with pytest.raises(ValueError, match=word):
            build_intake_from_args("outbound", [], lang="en", purpose="drafting", brief=bad)
    with pytest.raises(ValueError, match="outbound"):
        build_intake_from_args("inbound", [], lang="en", purpose="drafting", brief=BRIEF)
    with pytest.raises(ValueError, match="brief"):
        build_intake_from_args("outbound", [], lang="en", purpose="drafting")
    with pytest.raises(ValueError, match="purpose"):
        build_intake_from_args("outbound", ["x"], lang="en", purpose="write")


def test_brief_loads_from_json_and_toml(tmp_path):
    p = tmp_path / "b.json"
    p.write_text(json.dumps(BRIEF), encoding="utf-8")
    assert drafting.load_brief(p)["kind"] == "product"
    q = tmp_path / "b.toml"
    q.write_text('kind = "data"\nconfirmed = ["x"]\ndecision = "respond"\n', encoding="utf-8")
    assert drafting.load_brief(q)["decision"] == "respond"


# @S-drafting-003
def test_expose_without_a_confirmed_fact_stops(tmp_path):
    run = drafting_run(tmp_path, dict(BRIEF, confirmed=[]), posture="expose")
    b = backend()
    out, _ = draft(run, b)
    assert out["status"] == "stopped" and "confirmed fact" in out["reason"]
    assert b.calls == []


# @S-drafting-004
def test_near_duplicates_retried_once_then_dropped(tmp_path):
    run = drafting_run(tmp_path)
    same = writer_answer(version(), version("Apology First"))
    b = backend(writer=[same, same])
    out, _ = draft(run, b)
    writes = [c for c in b.calls if c["task"] == "draft"]
    assert len(writes) == 2 and "differ" in writes[1]["prompt"]
    assert [v["id"] for v in out["versions"]] == ["V1"] and "near_duplicate" in out["warnings"]
    # 80% alike under different approach names is a duplicate too
    run2 = drafting_run(tmp_path / "b")
    alike = writer_answer(version(), version("action first"))
    out2, _ = draft(run2, backend(writer=[alike, writer_answer()]))
    assert [v["id"] for v in out2["versions"]] == ["V1", "V2"] and not out2["warnings"]
    assert drafting.alike(version(), version("x"))
    assert not drafting.alike(version(), version("action first", V2_PARAS))


# @S-drafting-005
def test_blocking_questions_capped_and_asked(tmp_path):
    qs = [f"Question {i}?" for i in range(1, 6)]
    run = drafting_run(tmp_path)
    b = backend(writer=[writer_answer(questions=qs), writer_answer()])
    out, io = draft(run, b, interactive=True, answers=["a1", "a2", "a3", ""])
    writes = [c for c in b.calls if c["task"] == "draft"]
    assert len(writes) == 2 and "Question 3?" in io.text and "Question 4?" not in io.text
    assert "a3" in writes[1]["prompt"] and "user answers" in writes[1]["prompt"].lower()
    assert out["open_questions"] == []
    run2 = drafting_run(tmp_path / "b")
    b2 = backend(writer=writer_answer(questions=qs, contradictions=["C1 and A1 disagree"]))
    out2, _ = draft(run2, b2)
    from ant_pr_review.report import drafting_lines
    assert "C1 and A1 disagree" in "\n".join(drafting_lines(t, out2))
    assert len([c for c in b2.calls if c["task"] == "draft"]) == 1
    assert out2["open_questions"] == qs[:3]


# @S-drafting-006
def test_tier4_makes_holding_statements(tmp_path):
    run = drafting_run(tmp_path, dict(BRIEF, tier4=["injury"]))
    b = backend()
    out, _ = draft(run, b)
    w = next(c for c in b.calls if c["task"] == "draft")
    assert "holding statement" in (w["system"] + w["prompt"]).lower()
    assert out["tier4"] == ["injury"]
    from ant_pr_review.report import drafting_lines
    assert "counsel" in "\n".join(drafting_lines(t, out)).lower()


# @S-drafting-007 @N-drafting-001
def test_claim_register_is_enforced():
    brief = drafting.check_brief(BRIEF)
    text = "We are sorry. The fault caused burns. Our product is the safest. Revenue fell."
    claims = [{"text": "a faulty seal", "basis": ["C1"], "class": "public"},
              {"text": "The fault caused burns", "basis": ["A1"], "class": "public"},
              {"text": "Revenue fell", "basis": [], "class": "public"},
              {"text": "Our product is the safest", "basis": [], "class": "not_supportable"}]
    reg, why = drafting.register(claims, brief, text)
    assert [c["class"] for c in reg] == ["public", "needs_validation", "needs_validation",
                                         "not_supportable"]
    assert reg[1]["downgraded"] and not reg[0].get("downgraded")
    assert why and "safest" in why[0]
    _, why2 = drafting.register(claims[:3], brief, text)
    assert why2 == []
    _, why3 = drafting.register([{"text": "the supplier is Acme", "basis": ["C1"],
                                  "class": "internal"}], brief, "We name the supplier is Acme.")
    assert why3 and "internal" in why3[0]


# @S-drafting-008 @N-drafting-001
def test_placeholders_and_internal_notes():
    hits = drafting.deliverable_issues("Line one.\nWe replace it from [待查證].\nTODO: check")
    assert [(h["kind"], h["line"]) for h in hits] == [("placeholder", 2), ("internal", 3)]
    assert drafting.deliverable_issues("（內部備註）別說供應商")[0]["kind"] == "internal"
    assert drafting.deliverable_issues("From [to verify] onwards")[0]["kind"] == "placeholder"
    assert drafting.deliverable_issues("A clean statement with 3 dates.") == []


def test_export_gate_in_the_report(tmp_path):
    from ant_pr_review.report import export_final
    run = drafting_run(tmp_path)
    write_json(run.path("08-drafts/summary.json"), {"status": "done", "chosen": "V1"})
    run.path("08-drafts/V1.md").write_text("We replace it from [待查證].\n", encoding="utf-8")
    got = export_final(run)
    assert got["written"] is False and got["issues"][0]["kind"] == "placeholder"
    assert not run.path("10-final.md").exists()
    run.path("09-plans").mkdir(parents=True, exist_ok=True)
    run.path("09-plans/A.md").write_text("We replace it from 1 November.\n", encoding="utf-8")
    got = export_final(run)
    assert got["written"] is True and got["source"] == "09-plans/A.md"
    assert run.path("10-final.md").read_text(encoding="utf-8").startswith("We replace")
    # an export left from an earlier, clean report goes when the text is no longer clean
    run.path("09-plans/A.md").write_text("TODO: date\n", encoding="utf-8")
    assert export_final(run)["written"] is False and not run.path("10-final.md").exists()
    audit = make_run(tmp_path / "audit")
    assert export_final(audit) == {"applies": False}


# @S-drafting-009
def test_readability_checks_w1_to_w8():
    long_sentence = "This sentence " + "keeps going and going " * 12 + "until it ends."
    bad = version(paras=[para("We are sorry. " + long_sentence, "stance"),
                         para(" ".join(["word"] * 130) + ".", "facts"),
                         para("We regret any inconvenience caused and will act as soon as "
                              "possible.", "cause"),
                         para("The relevant departments will conduct a review of the best "
                              "process in the industry.", "other")],
                  w={"who": "we", "what": "x", "when": "", "where": "y", "why": "z", "how": "q"})
    ids = {h["id"] for h in drafting.w_checks(bad, "clarify_apologize")}
    assert ids == {"W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"}
    zh = version(paras=[para("我們深表遺憾，將盡快以業界領先的標準進行相關的處理動作。", "stance")],
                 w={"who": "我們", "what": "x", "when": "10月20日", "where": "y", "why": "z",
                    "how": "q"})
    zh_ids = {h["id"] for h in drafting.w_checks(zh, "clarify_apologize")}
    assert {"W3", "W4", "W5", "W6", "W8"} <= zh_ids and "W1" not in zh_ids
    assert drafting.w_checks(version(), "clarify_apologize") == []
    # the four parts are asked only of apologies and rebuttals
    assert "W3" not in {h["id"] for h in drafting.w_checks(zh, "promote")}


# @S-drafting-010 @S-drafting-012
def test_each_version_audited_by_the_same_matrix(tmp_path):
    run = drafting_run(tmp_path)
    before = sorted(p.name for p in run.path("04-reviews").glob("*/*.json")) \
        if run.path("04-reviews").exists() else []
    b = backend()
    out, _ = draft(run, b)
    units = [u["id"] for u in read_json(run.path("03-matrix.json"))["units"]]
    for vid in ("V1", "V2"):
        sub = run.path(f"08-drafts/{vid}")
        assert sorted(read_json(sub / "03-matrix.json")["units"][i]["id"]
                      for i in range(2)) == sorted(units)
        recs = load_records(drafting.Run(sub), "04-reviews")
        assert len(recs) == 2 * len(units)
        assert read_json(sub / "06-synthesis.json")["consolidated"]["provisional"] is True
    after = sorted(p.name for p in run.path("04-reviews").glob("*/*.json")) \
        if run.path("04-reviews").exists() else []
    assert before == after
    rv = next(c for c in b.calls if c["task"] == "draft_review")
    wr = next(c for c in b.calls if c["task"] == "draft")
    assert rv["model"] != wr["model"]
    st = out["stage"]
    assert st["status"] == "ok" and st["reviewer"] == M2 and st["issues"]["V2"][0]["kind"] == "tone"
    # a refused review is shown as not reviewed
    run2 = drafting_run(tmp_path / "b")
    out2, _ = draft(run2, backend(review=Result(model=M2, model_id="x", data=None,
                                                refused=True)))
    assert out2["stage"]["status"] == "refused"


# @S-drafting-011
def test_ranking_is_code_and_reason_needs_numbers(tmp_path):
    vs = [{"id": "V1", "disqualified": [], "verdict": "conditional", "top": 9, "rate": 0.5},
          {"id": "V2", "disqualified": [], "verdict": "go", "top": 4, "rate": 0.8},
          {"id": "V3", "disqualified": ["not supportable"], "verdict": "go", "top": 1,
           "rate": 1.0}]
    assert drafting.rank(vs) == ["V2", "V1", "V3"]
    assert drafting.rank([dict(vs[1], id="A", rate=0.6), dict(vs[1], id="B")]) == ["B", "A"]
    run = drafting_run(tmp_path)
    out, _ = draft(run, backend(reason={"reason": "V1 is calmer."}))
    assert out["recommended"] in ("V1", "V2")
    assert re.search(r"\d", out["reason"]) and out["reason_by"] == "code"
    run2 = drafting_run(tmp_path / "b")
    out2, _ = draft(run2, backend())
    assert out2["reason_by"] == M2 and "100%" in out2["reason"]
    assert out2["recommended"] == "V1"  # equal numbers: the first version keeps its place
    # every version disqualified: the run pauses
    bad = {"text": "Our product is the safest", "basis": [], "class": "not_supportable"}
    v1 = version(paras=[para("Our product is the safest.", "stance")], claims=[bad])
    v2 = version("action first", [para("Our product is the safest. Stop using it.", "stance")],
                 claims=[bad])
    run3 = drafting_run(tmp_path / "c")
    out3, _ = draft(run3, backend(writer=writer_answer(v1, v2)))
    assert out3["status"] == "stopped" and "disqualified" in out3["reason"]


# @S-drafting-013
def test_the_recommended_version_becomes_the_source(tmp_path):
    run = drafting_run(tmp_path)
    out, _ = draft(run, backend())
    segs = read_json(run.path("01-sources/segments.json"))
    text = " ".join(s["text"] for doc in segs.values() for s in doc)
    chosen = out["chosen"]
    assert chosen == out["recommended"]
    assert run.path(f"08-drafts/{chosen}.md").read_text(encoding="utf-8").split("\n")[0] \
        .lstrip("# ") in text
    # interactively another version may be picked
    run2 = drafting_run(tmp_path / "b")
    out2, _ = draft(run2, backend(), interactive=True, answers=["2"])
    other = [v["id"] for v in out2["versions"] if v["id"] != out2["recommended"]][0]
    assert out2["chosen"] == other
    segs2 = json.dumps(read_json(run2.path("01-sources/segments.json")), ensure_ascii=False)
    first = next(p["text"] for v in out2["versions"] if v["id"] == other
                 for p in v["paragraphs"][:1])
    assert first[:20] in segs2


def test_an_audit_run_has_no_draft(tmp_path):
    run = make_run(tmp_path)
    b = backend()
    out, _ = draft(run, b)
    assert out["status"] == "not_applicable" and b.calls == []


def test_a_rerun_with_the_same_inputs_reuses_the_writer(tmp_path):
    run = drafting_run(tmp_path)
    draft(run, backend())
    b = backend()
    draft(run, b)
    assert not [c for c in b.calls if c["task"] in ("draft", "review")]


def test_a_failed_writer_raises_for_a_pause(tmp_path):
    run = drafting_run(tmp_path)
    with pytest.raises(BackendError):
        draft(run, backend(writer=BackendError("slow", reason="timeout")))


# @S-drafting-014
def test_report_shows_the_drafting_section(tmp_path):
    from ant_pr_review.report import drafting_lines
    run = drafting_run(tmp_path)
    out, _ = draft(run, backend())
    text = "\n".join(drafting_lines(t, out))
    for v in out["versions"]:
        assert v["approach"] in text
    assert "Decision: Publish" in text and "Recommended: V" in text and "100%" in text and out["reason"] in text
    assert "public" in text and "stiff" in text and "█" in text


# @S-drafting-015 @N-drafting-002
def test_examples_by_posture_and_ethics():
    ex = drafting.examples_for("clarify_apologize")
    assert 0 < len(ex) <= 6 and all(e["posture"] == "clarify_apologize" for e in ex)
    assert {e["kind"] for e in ex} == {"pattern", "counter"}
    allx = drafting.examples_for("clarify_apologize", limit=99) + \
        drafting.examples_for("rebut", limit=99)
    # @S-drafting-015 no third-party text: lessons are paraphrased, nothing is quoted
    assert all(e["verified"] is False and "quote" not in e for e in allx)
    raw = (Path(drafting.__file__).parent / "examples.toml").read_text(encoding="utf-8")
    assert "\nquote" not in raw
    assert "Quote:" not in drafting.examples_block(allx)
    block = drafting.examples_block(ex)
    assert "unverified" in block.lower() and "counter" in block.lower()
    from ant_pr_review.prompts import draft_system
    s = draft_system("en", {"posture": "clarify_apologize", "means": ["white", "gray", "black"]},
                     tier4=False)
    assert "never" in s.lower() and "black" in s.lower()


def test_ethics_guard_runs_on_every_version(tmp_path):
    run = drafting_run(tmp_path)
    sock = version("action first", [para("Post this from many accounts so it looks organic.",
                                         "measures")] + V2_PARAS)
    clean = writer_answer()
    b = backend(writer=[writer_answer(v2=sock), clean])
    out, _ = draft(run, b)
    writes = [c for c in b.calls if c["task"] == "draft"]
    assert len(writes) == 2 and out["ethics"]["first"]
    assert "many accounts" not in json.dumps(out["versions"], ensure_ascii=False)
    from ant_pr_review import ethics
    assert ethics.scan_text("讓這篇看起來像是自發的討論")
    assert not ethics.scan_text("Many accounts were affected by the breach.")


# @S-drafting-013 @S-drafting-014 end to end through the CLI with the offline backend
def test_cli_drafting_run_end_to_end(tmp_path, store):
    from ant_pr_review import cli
    p = tmp_path / "brief.json"
    p.write_text(json.dumps(dict(BRIEF, confirmed=["A fault in our service was confirmed"])),
                 encoding="utf-8")

    class NoAsk(ScriptedIO):
        def ask(self, prompt):
            raise AssertionError(f"asked: {prompt}")
    code = cli.main(["new", "--yes", "--backend", "fake", "--brief", str(p)], io=NoAsk(),
                    store=store)
    run = next(store.runs_dir.iterdir())
    assert run.name.split("-", 2)[-1].startswith("draft")
    assert cli.summary_rows(store)[0]["title"].startswith("A fault in our service")
    summary = read_json(run / "08-drafts/summary.json")
    assert summary["status"] == "done" and summary["chosen"] in ("V1", "V2")
    report = next(run.glob("08-report.v1.md")).read_text(encoding="utf-8")
    assert "## Drafting" in report and "Claim register" in report
    meta = read_json(run / "08-report.v1.json")["final"]
    if meta["written"]:
        assert (run / "10-final.md").read_text(encoding="utf-8") == \
            (run / meta["source"]).read_text(encoding="utf-8")
    else:  # blocked: the report is still written and names what blocks
        assert not (run / "10-final.md").exists() and "No ready-to-publish file" in report
    assert code in (0, 3)  # done, or paused at the decision a --yes run never makes


# @S-drafting-012 a model never reviews its own drafts
def test_one_model_roster_skips_the_draft_review(tmp_path):
    run = drafting_run(tmp_path, models=(M1,))
    b = backend()
    out = drafting.run_draft(run, b, [M1], "en", DEFAULT_THRESHOLDS, io=ScriptedIO([]),
                             interactive=False, say=lambda *a: None)
    assert out["stage"]["status"] == "skipped" and out["stage"]["reason"] == "same_model"
    assert not [c for c in b.calls if c["task"] == "draft_review"]


# ---- tier-3 review findings ----------------------------------------------------------

SOCK = "Post this from many accounts so it looks organic."


# @S-drafting-004 @N-drafting-002 the near-duplicate fallback is scanned too
def test_near_duplicate_fallback_is_scanned(tmp_path):
    run = drafting_run(tmp_path)
    same = writer_answer(version(), version("Apology First"))
    dirty = version(paras=[para(SOCK, "measures")] + V2_PARAS)
    b = backend(writer=[same, {"versions": [dirty], "blocking_questions": [],
                               "contradictions": [SOCK]}])
    out, _ = draft(run, b)
    dumped = json.dumps([out["versions"], out["contradictions"]], ensure_ascii=False)
    assert "many accounts" not in dumped and out["ethics"]["final"]


# @N-drafting-002 a cached writer output is scanned again
def test_cached_versions_are_rescanned(tmp_path):
    run = drafting_run(tmp_path)
    draft(run, backend())
    w = read_json(run.path("08-drafts/writer.json"))
    w["versions"][0]["paragraphs"][0]["text"] = SOCK
    write_json(run.path("08-drafts/writer.json"), w)
    out, _ = draft(run, backend())
    assert "many accounts" not in json.dumps(out["versions"], ensure_ascii=False)


# @S-drafting-011 a version no reviewer answered is never recommended
def test_unaudited_version_is_disqualified(tmp_path):
    run = drafting_run(tmp_path)
    calls = {"n": 0}

    def review(prompt):
        if "action first" in prompt or "please stop using" in prompt.lower():
            return BackendError("down", reason="offline")
        return auto_review(verdicts=None)(prompt)
    b = backend()
    b.handlers[("*", "review")] = review
    out, _ = draft(run, b)
    v2 = next(v for v in out["versions"] if v["id"] == "V2")
    assert v2["disqualified"] and out["recommended"] == "V1"
    run2 = drafting_run(tmp_path / "b")
    b2 = backend()
    b2.handlers[("*", "review")] = BackendError("down", reason="offline")
    with pytest.raises(BackendError):
        draft(run2, b2)


# @S-drafting-011 the reason must cite the recommended version's own figures
def test_reason_must_cite_the_real_figures(tmp_path):
    for i, reason in enumerate(("推薦V1，因為判定較佳。", "V1 is best in 2 ways.",
                                "V2 wins with 100%.", "V1 is better per 5W1H.")):
        run = drafting_run(tmp_path / str(i))
        out, _ = draft(run, backend(reason={"reason": reason}))
        assert out["reason_by"] == "code", reason


# @S-drafting-008 placeholder variants
def test_placeholder_variants():
    for s in ("[待查證：日期]", "[to verify: date]", "【待查證】", "〔待查證〕", "[ 待查證 ]",
              "[insert name]", "□□", "____", "待查證", "[TBD]"):
        assert drafting.deliverable_issues(f"From {s} on.")[0]["kind"] in ("placeholder",
                                                                           "internal"), s
    assert drafting.deliverable_issues("Size XXL and [1] footnote, 3 Mar.") == []


# @S-drafting-008 @N-drafting-001 a stopped draft leaves no export; a needs-validation
# claim or a figure the revision invented blocks it
def test_export_gate_hardened(tmp_path):
    from ant_pr_review.report import export_final
    run = drafting_run(tmp_path)
    out, _ = draft(run, backend())
    chosen = out["chosen"]
    assert export_final(run)["written"] is True
    write_json(run.path("08-drafts/summary.json"), dict(out, status="stopped"))
    assert export_final(run)["applies"] is False and not run.path("10-final.md").exists()
    write_json(run.path("08-drafts/summary.json"), out)
    text = run.path(f"08-drafts/{chosen}.md").read_text(encoding="utf-8")
    run.path("09-plans").mkdir(parents=True, exist_ok=True)
    run.path("09-plans/A.md").write_text(text + "\nRefunds reach you within 14 days.\n",
                                         encoding="utf-8")
    got = export_final(run)
    assert got["written"] is False and got["issues"][0]["kind"] == "new_figure"
    assert "14" in got["issues"][0]["match"]
    v = next(x for x in out["versions"] if x["id"] == chosen)
    v["claims"].append({"text": "The fault caused burns", "basis": ["A1"],
                        "class": "needs_validation", "in_text": True})
    write_json(run.path("08-drafts/summary.json"), out)
    run.path("09-plans/A.md").write_text(text + "\nThe fault caused burns.\n", encoding="utf-8")
    got = export_final(run)
    assert got["written"] is False and got["issues"][0]["kind"] == "needs_validation"
    # the draft phase itself removes an earlier export
    run.path("10-final.md").write_text("old", encoding="utf-8")
    draft(run, backend())
    assert not run.path("10-final.md").exists()


# @S-drafting-007 a public claim needs every basis confirmed
def test_public_claim_needs_only_confirmed_basis():
    brief = drafting.check_brief(BRIEF)
    reg, _ = drafting.register([{"text": "x", "basis": ["C1", "A1"], "class": "public"}],
                               brief, "x")
    assert reg[0]["class"] == "needs_validation"


def test_organic_pattern_is_narrow():
    from ant_pr_review import ethics
    assert ethics.scan_text("Post it from many accounts so it looks organic.")
    assert ethics.scan_text("Make them appear spontaneous.")
    assert not ethics.scan_text("The protests appear spontaneous to observers.")


# @S-drafting-008 @N-drafting-002 the guard's own marker is an internal note
def test_ethics_marker_blocks_the_export():
    from ant_pr_review.ethics import MARK
    assert drafting.deliverable_issues("Hi. " + MARK.format(cat="persona"))[0]["kind"] == \
        "internal"


# @S-drafting-008 no export while the verdict asks for a lawyer or forbids publishing
def test_export_withheld_on_escalate_or_no_go(tmp_path):
    from ant_pr_review.report import export_final
    run = drafting_run(tmp_path)
    draft(run, backend())
    for verdict in ("escalate", "no_go"):
        write_json(run.path("06-synthesis.json"), {"consolidated": {"verdict": verdict}})
        got = export_final(run)
        assert got["written"] is False and got["issues"][0]["kind"] == "verdict"
    write_json(run.path("06-synthesis.json"), {"consolidated": {"verdict": "conditional"}})
    assert export_final(run)["written"] is True


# @S-drafting-005 a question the guard flags is never asked; questions are cleaned
def test_blocking_questions_are_scanned_and_cleaned(tmp_path):
    run = drafting_run(tmp_path)
    b = backend(writer=[writer_answer(questions=["When\x1b[31m is the recall?"]),
                        writer_answer()])
    out, io = draft(run, b, interactive=True, answers=["1 Nov", ""])
    assert "\x1b[31m" not in io.text and "When is the recall?" in " ".join(io.text.split())
    assert drafting._questions({"blocking_questions": ["Which sockpuppet accounts can we use?",
                                                       "Who approves?"]}) == ["Who approves?"]


def test_rerun_from_draft_writes_again(tmp_path, store):
    from ant_pr_review import cli
    p = tmp_path / "brief.json"
    p.write_text(json.dumps(BRIEF), encoding="utf-8")

    class NoAsk(ScriptedIO):
        def ask(self, prompt):
            raise AssertionError(f"asked: {prompt}")
    cli.main(["new", "--yes", "--backend", "fake", "--brief", str(p)], io=NoAsk(), store=store)
    run = next(store.runs_dir.iterdir())
    w = read_json(run / "08-drafts/writer.json")
    write_json(run / "08-drafts/writer.json", dict(w, marker=1))
    cli.main(["rerun", run.name, "--from", "draft", "--yes", "--backend", "fake"], io=NoAsk(),
             store=store)
    assert "marker" not in read_json(run / "08-drafts/writer.json")  # written afresh


def test_unreadable_material_does_not_block_drafting(tmp_path, store):
    from ant_pr_review import cli
    p = tmp_path / "brief.json"
    p.write_text(json.dumps(BRIEF), encoding="utf-8")

    class NoAsk(ScriptedIO):
        def ask(self, prompt):
            raise AssertionError(f"asked: {prompt}")
    cli.main(["new", "--yes", "--backend", "fake", "--brief", str(p), "--target",
              "https://127.0.0.1:9/notes"], io=NoAsk(), store=store)
    run = next(store.runs_dir.iterdir())
    assert read_json(run / "08-drafts/summary.json")["status"] == "done"


def test_malformed_model_output_is_tolerated():
    brief = drafting.check_brief(BRIEF)
    reg, _ = drafting.register([{"text": "x", "basis": None, "class": "public"}], brief, "x")
    assert reg[0]["class"] == "needs_validation"
