"""Drafting: the holding gate, cannot-commit lines, W9 and fast actions, slow conclusions
(D-0005, from the brake-pedal commentary videos)."""
import pytest

from ant_pr_review import drafting, prompts
from ant_pr_review.intake import build_intake_from_args, run_intake_interactive
from ant_pr_review.jsonio import write_json
from ant_pr_review.ui import ScriptedIO
from test_drafting import BRIEF, backend, draft, drafting_run, para, t, version


def writer_call(b):
    w = next(c for c in b.calls if c["task"] == "draft")
    return w["system"] + w["prompt"]


# @S-drafting-017
def test_brief_asks_characterised_and_cannot_commit():
    answers = ["3", "", "", "", "",
               "1", "A batch shipped with a faulty seal", "/done", "/done", "/done", "", "", "", "",
               "buyers", "", "", "",
               "/done", "/done", "/done", "/done",
               "legal",
               "2",                              # characterised: yes
               "召回", "承認缺陷", "/done",        # cannot commit
               "",                               # tier-4: none
               "/done"]
    from test_context_card import FILL
    io = ScriptedIO(answers + FILL[:-3] + [""])
    b = run_intake_interactive(io, t, "en")["brief"]
    assert b["characterised"] is True and b["cannot_commit"] == ["召回", "承認缺陷"]
    assert "cause and scope" in io.text
    b = build_intake_from_args("outbound", [], lang="en", purpose="drafting", brief=BRIEF)["brief"]
    assert b["characterised"] is False and b["cannot_commit"] == []
    b = drafting.check_brief(dict(BRIEF, characterised=True, cannot_commit="全額賠償"))
    assert b["characterised"] is True and b["cannot_commit"] == ["全額賠償"]
    with pytest.raises(ValueError, match="characterised"):
        drafting.check_brief(dict(BRIEF, characterised="maybe"))


# @S-drafting-018
def test_not_characterised_gives_holding_statements(tmp_path):
    run = drafting_run(tmp_path)
    b = backend()
    out, _ = draft(run, b)
    assert "holding statements only" in writer_call(b)
    assert out["holding"] is True
    from ant_pr_review.report import drafting_lines
    assert "do not yet characterise" in "\n".join(drafting_lines(t, out))
    run = drafting_run(tmp_path / "b", dict(BRIEF, characterised=True))
    b = backend()
    out, _ = draft(run, b)
    assert "holding statements only" not in writer_call(b) and out["holding"] is False
    assert "do not yet characterise" not in "\n".join(drafting_lines(t, out))
    run = drafting_run(tmp_path / "c", dict(BRIEF, characterised=True, tier4=["injury"]))
    b = backend()
    out, _ = draft(run, b)
    assert "holding statements only" in writer_call(b) and out["holding"] is True


# @S-drafting-019
def test_cannot_commit_lines_found_and_block_export(tmp_path):
    v = version(paras=[para("我們將召回 3 月批次。", "measures")])
    assert drafting.bound_hits(v, ["召回", "全額賠償"]) == ["召回"]
    assert drafting.bound_hits(version(), ["召回"]) == []
    # case and spacing do not hide a hit
    assert drafting.bound_hits("We give a full  refund.", ["Full Refund"]) == ["Full Refund"]
    from ant_pr_review.report import drafting_lines, export_final, export_lines
    brief = dict(BRIEF, cannot_commit=["recall"])
    run = drafting_run(tmp_path, brief)
    out, _ = draft(run, backend())
    assert all(v["bounds"] == [] for v in out["versions"])
    hit = drafting_run(tmp_path / "hit", dict(BRIEF, cannot_commit=["replace it FREE"]))
    out_hit, _ = draft(hit, backend())
    assert [v["bounds"] for v in out_hit["versions"]] == [["replace it FREE"], []]
    assert export_final(run)["written"] is True
    run.path("09-plans").mkdir(parents=True, exist_ok=True)
    run.path("09-plans/A.md").write_text("We start a Recall of the March batch.\n",
                                         encoding="utf-8")
    got = export_final(run)
    assert got["written"] is False and not run.path("10-final.md").exists()
    assert [i["kind"] for i in got["issues"]] == ["cannot_commit"]
    assert "commit to" in "\n".join(export_lines(t, got))
    out["versions"][0]["bounds"] = ["recall"]
    assert "recall" in "\n".join(drafting_lines(t, out))


# @S-drafting-020
def test_w9_vague_quantity_without_a_number():
    bad = version(paras=[para("個別車輛的踏板支架可能鬆動。", "facts"),
                         para("Some units may be affected.", "facts")])
    hits = [h for h in drafting.w_checks(bad, "promote") if h["id"] == "W9"]
    assert [h["where"] for h in hits] == ["P1", "P2"]
    good = version(paras=[para("個別車輛（3 輛）的踏板支架可能鬆動。", "facts"),
                          para("Some units (12) may be affected.", "facts")])
    assert not [h for h in drafting.w_checks(good, "promote") if h["id"] == "W9"]
    assert t("draft.w.W9") != "draft.w.W9"


# @S-drafting-021
def test_fast_actions_slow_conclusions_in_prompts():
    s = prompts.draft_system("en", {"posture": "rebut", "means": ["white"]}, tier4=False)
    for needle in ("Fast actions, slow conclusions", "no defect", "what the fix is for",
                   "cannot_commit"):
        assert needle in s, needle
    assert {"early_conclusion", "commitment_crossed"} <= set(drafting.DRAFT_REVIEW_KINDS)
    r = prompts.draft_review_system("en")
    assert "early_conclusion" in r and "commitment_crossed" in r
    for k in ("early_conclusion", "commitment_crossed"):
        assert t(f"draft.issue.{k}") != f"draft.issue.{k}"


# @S-drafting-017 short lines and the US spelling
def test_short_lines_refused_and_spelling():
    for bad in ("召", "。", "ab", "a-b"):
        with pytest.raises(ValueError, match="cannot_commit"):
            drafting.check_brief(dict(BRIEF, cannot_commit=[bad]))
    assert drafting.check_brief(dict(BRIEF, characterized=True))["characterised"] is True
    assert drafting.check_brief(dict(BRIEF, cannot_commit=["召回。"]))["cannot_commit"] == ["召回"]
    answers = ["3", "", "", "", "",
               "1", "A batch shipped with a faulty seal", "/done", "/done", "/done", "", "", "", "",
               "buyers", "", "", "", "/done", "/done", "/done", "/done", "legal", "",
               "召", "/done",            # too short: asked again
               "召回", "/done", "", "/done"]
    from test_context_card import FILL
    io = ScriptedIO(answers + FILL[:-3] + [""])
    b = run_intake_interactive(io, t, "en")["brief"]
    assert b["cannot_commit"] == ["召回"] and "too short" in io.text.lower()


# @S-drafting-019 punctuation, negation, ranking, the chosen-version path and plan A
def test_bounds_matching_ranking_and_paths(tmp_path):
    assert drafting.bound_hits("A full refund.", ["full-refund"]) == ["full-refund"]
    assert drafting.bound_hits("We will not​ recall it.", ["recall"]) == ["recall"]
    assert drafting.bound_hits("We start a recall.", ["recall."]) == ["recall."]
    from ant_pr_review.report import export_final
    run = drafting_run(tmp_path, dict(BRIEF, cannot_commit=["replace it FREE"]))
    out, _ = draft(run, backend())
    assert out["versions"][0]["bounds"] and not out["versions"][1]["bounds"]
    assert out["order"][0] == "V2" and out["recommended"] == "V2"
    # the chosen version is the final text when there is no revision
    write_json(run.path("08-drafts/summary.json"), dict(out, chosen="V1"))
    got = export_final(run)
    assert got["written"] is False and "cannot_commit" in [i["kind"] for i in got["issues"]]
    # the plan A writer is told the lines
    from ant_pr_review import prompts as P
    from ant_pr_review.jsonio import read_json
    intake = read_json(run.path("00-intake.json"))
    assert "replace it FREE" in P.plan_prompt([], "text", intake)
    audit = build_intake_from_args("outbound", ["x"], lang="en")
    assert "must not concede" not in P.plan_prompt([], "text", audit)


def test_pick_marks_a_version_with_a_hit(tmp_path):
    run = drafting_run(tmp_path, dict(BRIEF, cannot_commit=["replace it FREE"]))
    out, io = draft(run, backend(), interactive=True, answers=[""])
    assert "⚠" in io.text and out["chosen"] == "V2"


def test_schema_enum_matches_review_kinds():
    from ant_pr_review.schemas import DRAFT_REVIEW
    kinds = DRAFT_REVIEW["properties"]["versions"]["items"]["properties"]["issues"]["items"] \
        ["properties"]["kind"]["enum"]
    assert kinds == drafting.DRAFT_REVIEW_KINDS


def test_an_old_brief_without_the_new_keys(tmp_path):
    from ant_pr_review.report import drafting_lines, export_final
    run = drafting_run(tmp_path)
    from ant_pr_review.jsonio import read_json
    intake = read_json(run.path("00-intake.json"))
    for k in ("characterised", "cannot_commit"):
        intake["brief"].pop(k)
    write_json(run.path("00-intake.json"), intake)
    out, _ = draft(run, backend())
    assert out["holding"] is True and all(v["bounds"] == [] for v in out["versions"])
    assert export_final(run)["applies"] is True
    assert drafting_lines(t, out)


def test_writer_cache_follows_the_prompt(tmp_path, monkeypatch):
    run = drafting_run(tmp_path)
    b = backend()
    draft(run, b)
    n = sum(c["task"] == "draft" for c in b.calls)
    draft(run, b)
    assert sum(c["task"] == "draft" for c in b.calls) == n      # cached
    monkeypatch.setattr(prompts, "draft_system", lambda *a, **k: "changed rules")
    draft(run, b)
    assert sum(c["task"] == "draft" for c in b.calls) > n       # a new prompt is not replayed


# @S-drafting-020 narrowed
def test_w9_narrowed():
    def w9(text):
        return [h for h in drafting.w_checks(version(paras=[para(text)]), "promote")
                if h["id"] == "W9"]
    assert w9("On 20 October some units failed.")
    for clean in ("我們會個別通知每位車主。", "The server was isolated from the network.",
                  "Some of you have written to us.", "少數民族地區的門市照常營業。"):
        assert not w9(clean), clean


# @S-drafting-022
def test_decide_checks_the_final_file_of_a_drafting_run(tmp_path):
    from ant_pr_review.decision import final_issues_for
    run = drafting_run(tmp_path, dict(BRIEF, cannot_commit=["recall"]))
    draft(run, backend())
    run.path("09-plans").mkdir(parents=True, exist_ok=True)
    run.path("09-plans/A.md").write_text("We start a recall.\n", encoding="utf-8")
    run.path("final.md").write_text("We start a recall.\n", encoding="utf-8")
    assert [i["kind"] for i in final_issues_for(run)] == ["cannot_commit"]
    run.path("final.md").write_text("We replace units.\n", encoding="utf-8")
    assert final_issues_for(run) == []
    # an audit run's decision is unchanged, whatever files lie around
    from ant_pr_review.jsonio import read_json
    intake = read_json(run.path("00-intake.json"))
    write_json(run.path("00-intake.json"), dict(intake, purpose="audit"))
    run.path("final.md").write_text("We start a recall.\n", encoding="utf-8")
    assert final_issues_for(run) == []


# @S-drafting-022 through decide
def test_decide_records_and_shows_the_issues(tmp_path):
    from ant_pr_review.decision import run_decision
    from ant_pr_review.jsonio import read_json
    from ant_pr_review.refresh import compute_synthesis
    from ant_pr_review.review import run_round1
    from ant_pr_review.store import DEFAULT_THRESHOLDS, Store
    from helpers import M1, M2, ScriptBackend, auto_review
    run = drafting_run(tmp_path, dict(BRIEF, cannot_commit=["recall"]))
    draft(run, backend())
    run_round1(run, ScriptBackend({("*", "review"): auto_review()}), [M1, M2], "en",
               say=lambda *_: None)
    compute_synthesis(run, [M1, M2], DEFAULT_THRESHOLDS)
    run.path("09-plans").mkdir(parents=True, exist_ok=True)
    run.path("09-plans/A.md").write_text("We start a recall.\n", encoding="utf-8")
    io = ScriptedIO([])
    dec = run_decision(io, run, Store(tmp_path / "home"), models=[M1, M2], lang="en",
                       thresholds=DEFAULT_THRESHOLDS, min_repeats=3, choice="A")
    assert run.path("final.md").read_text(encoding="utf-8") == "We start a recall.\n"
    assert [i["kind"] for i in dec["issues"]] == ["cannot_commit"]
    assert read_json(run.path("10-decision.json"))["issues"] == dec["issues"]
    assert "ready to publish" in io.text
