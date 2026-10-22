from ant_pr_review import ethics
from ant_pr_review.factcheck import write_ledger
from ant_pr_review.jsonio import read_json, write_json
from ant_pr_review.plans import run_plans
from ant_pr_review.revision import apply_changes, char_diff, paragraphs, render_text
from ant_pr_review.roster import slug
from ant_pr_review.schemas import PLAN_B_OPERATION
from helpers import M1, M2, ScriptBackend, make_run, ok, review_data

Q = lambda *_: None
TEXT = "# 標題\n\n我們的產品很棒棒，大家都喜翻。\n\nA公司的手機曾經爆炸。 Second sentence."
RISK = {"id": "R01", "anchor": "D1.P03.S1", "dimension": "provability", "scope": "tw",
        "scenario": "s", "standard": "std", "mitigation": "m", "score": 12}
KIT = {"holding_statement": "We are looking into it.", "qa": [], "monitoring_keywords": [],
       "escalation": [], "do_not_say": []}
B_OUT = {"recommendation": "publish_revised", "headline_options": [], "paragraphs": [],
         "alternative": "", "notes": ""}
RR = {"verdicts": [{"issue": "R01", "verdict": "FULLY", "note": ""}]}


def setup(tmp_path, direction="outbound", models=(M1, M2)):
    run = make_run(tmp_path, text=TEXT, direction=direction, models=models)
    for m in models:
        write_json(run.path(f"04-reviews/tw.all/{slug(m)}.json"), ok(m, "tw.all", review_data()))
    write_json(run.path("06-synthesis.json"), {"risks": [RISK], "unverified": [],
                                               "jurisdictions": {}})
    return run


def backend(over=None):
    h = {(M1, "plan_a"): {"paragraphs": [{"id": "D1.P02", "text": "我們的產品很棒，大家都喜歡。"}],
                          "corrections": []},
         (M1, "plan_b"): B_OUT, (M1, "kit"): KIT, ("*", "rereview"): RR}
    h.update(over or {})
    return ScriptBackend(h)


# @S-plans-001
def test_char_diff(tmp_path):
    assert char_diff("很棒棒", "很棒") == "很棒[-棒-]"
    run = setup(tmp_path)
    run_plans(run, backend(), [M1, M2], "en", say=Q)
    diff = run.path("09-plans/A.diff").read_text()
    assert "@@ D1.P02 @@" in diff and "很棒[-棒-]" in diff and "喜[-翻-]{+歡+}" in diff


# @S-plans-002
def test_each_direction_gets_its_plans(tmp_path):
    out = run_plans(setup(tmp_path / "o"), backend(), [M1, M2], "en", say=Q)
    assert out["plans"] == ["A", "B"] and "C" in out["ethics"]
    op = setup(tmp_path / "p", direction="operation")
    b = backend({(M1, "plan_b"): {"recommendation": "do_not_proceed", "alternative_plan": "",
                                    "rationale": "r", "addresses": ["R01"]}})
    out = run_plans(op, b, [M1, M2], "en", say=Q)
    assert out["plans"] == ["B"] and not op.path("09-plans/A.md").exists()
    assert [c["schema"] for c in b.calls if c["task"] == "plan_b"] == [PLAN_B_OPERATION]
    assert "do not proceed" in op.path("09-plans/B.md").read_text()
    inb = setup(tmp_path / "i", direction="inbound")
    b = backend({(M1, "plan_b"): {"options": [{"option": "clarify", "when": "now",
                                                 "risks": "few", "addresses": ["R01"]}],
                                    "recommended": "clarify", "statement_draft": "Facts."}})
    out = run_plans(inb, b, [M1, M2], "en", say=Q)
    assert out["plans"] == ["B"] and "| clarify | now | few | R01 |" in \
        inb.path("09-plans/B.md").read_text()
    for r in (op, inb):
        assert r.path("09-plans/C-kit.md").exists()


# @S-plans-003
def test_rereview_by_another_vendor(tmp_path):
    models = [M1, "claude:sonnet", M2]
    run = setup(tmp_path, models=models)
    b = backend()
    out = run_plans(run, b, models, "en", say=Q)
    assert out["writer"] == M1 and out["checker"] == M2
    assert [c["model"] for c in b.calls if c["task"] == "rereview"] == [M2, M2, M2]  # A, B, C
    assert read_json(run.path("09-plans/rereview.json"))["A"][0]["verdict"] == "FULLY"


# @S-plans-004
def test_unknown_ids_ignored(tmp_path):
    run = setup(tmp_path)
    out = run_plans(run, backend({(M1, "plan_a"): {"paragraphs": [{"id": "D9.P99",
                                                                      "text": "x"}],
                                                     "corrections": []}}), [M1, M2], "en", say=Q)
    assert any("D9.P99" in w for w in out["warnings"])
    assert "很棒棒" in run.path("09-plans/A.md").read_text()


# @S-plans-005
def test_sentence_ids_and_inserts(tmp_path):
    run = make_run(tmp_path, text="# T\n\nOld one. Keep two.\n\nLast para.")
    paras = paragraphs(run)
    rep, warn = apply_changes(paras, [{"id": "D1.P02.S1", "text": "New one."},
                                      {"id": "D1.P02+", "text": "Inserted para."}])
    assert warn == []
    assert render_text(paras, rep) == "# T\n\nNew one. Keep two.\n\nInserted para.\n\nLast para.\n"


# @S-plans-006
def test_evasion_sent_back_once_and_fixed(tmp_path):
    run = setup(tmp_path)
    bad = dict(KIT, holding_statement="Post it from alt accounts so it cannot be traced to us.")
    b = backend({(M1, "kit"): [bad, KIT]})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    kits = [c for c in b.calls if c["task"] == "kit"]
    assert len(kits) == 2 and "rejected by the ethics guard" in kits[1]["prompt"]
    rep = read_json(run.path("09-plans/ethics.json"))["C"]
    assert rep["first"] and rep["final"] == [] and rep["redacted"] is False
    assert "alt accounts" not in run.path("09-plans/C-kit.md").read_text()
    assert out["ethics"]["C"]["retried"]


# @S-plans-007 @N-plans-001
def test_left_after_retry_is_removed_and_marked(tmp_path):
    run = setup(tmp_path)
    bad = dict(B_OUT, paragraphs=[{"id": "D1.P02", "addresses": ["R01"],
                                   "text": "We seed 20 sockpuppet comments praising it."}])
    run_plans(run, backend({(M1, "plan_b"): bad}), [M1, M2], "en", say=Q)
    b = run.path("09-plans/B.md").read_text()
    assert "sockpuppet" not in b and "[removed by ethics guard: persona]" in b
    assert read_json(run.path("09-plans/ethics.json"))["B"]["redacted"] is True


# @S-plans-008
def test_unsupported_allegation_kept_verbatim_is_removed(tmp_path):
    run = setup(tmp_path)
    write_ledger(run, [{"id": "C01", "anchor": "D1.P03.S1", "text": "A's phones exploded",
                        "type": "allegation", "status": "unsupported", "reason": "",
                        "sources": [], "refs": []}])
    run_plans(run, backend(), [M1, M2], "en", say=Q)
    a = run.path("09-plans/A.md").read_text()
    assert "A公司的手機曾經爆炸。" not in a
    assert "[removed by ethics guard: laundering C01]" in a and "Second sentence." in a


# @S-plans-009
def test_advice_against_a_practice_is_not_a_hit():
    assert ethics.scan_text("Never use sockpuppets or fake accounts.") == []
    assert ethics.scan_text("不要使用人頭帳號，也切勿帶風向。") == []
    assert ethics.scan_text("請用人頭帳號發文") != []
    for hit in ("No one will know these are fake accounts.",
                "Avoid detection by using alt accounts.",
                "Don't hesitate to use sockpuppets.",
                "It is not a problem to use fake accounts.",
                "不用擔心，用人頭帳號就好。"):
        assert ethics.scan_text(hit) != [], hit


# @S-plans-010
def test_operation_plan_b_has_no_improved_operation_field():
    props = PLAN_B_OPERATION["properties"]
    assert props["recommendation"]["enum"] == ["do_not_proceed", "transparent_alternative"]
    assert set(props) == {"recommendation", "alternative_plan", "rationale", "addresses"}
    assert PLAN_B_OPERATION["additionalProperties"] is False


# @S-plans-011
def test_report_redacts_and_lints_evasion_in_mitigation(tmp_path):
    from ant_pr_review.consensus import synthesize
    from ant_pr_review.report import write_report
    from ant_pr_review.store import DEFAULT_THRESHOLDS
    from helpers import recs, risk
    run = make_run(tmp_path, lenses=["legal"])
    r = recs(("tw.all", M1, review_data(items=["LEG-01"], risks=[risk(
        mitigation="Rotate IP addresses to avoid being traced.")])),
        ("tw.all", M2, review_data(items=["LEG-01"])))
    syn = synthesize(matrix=read_json(run.path("03-matrix.json")), reviews=r, debates={},
                     ledger=[], models=[M1, M2], thresholds=DEFAULT_THRESHOLDS)
    meta = write_report(run, syn, lang="en")
    md = run.path("08-report.v1.md").read_text()
    assert "Rotate IP" not in md and "removed by ethics guard: evasion" in md
    assert any("ethics guard (evasion)" in p for p in meta["lint"])
