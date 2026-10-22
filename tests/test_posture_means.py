"""Posture, means, the timeline, locked sentences, the re-audit and stage reviews (D-0002)."""
import hashlib

import pytest

from ant_pr_review import prompts
from ant_pr_review.backends.base import BackendError
from ant_pr_review.catalog import (DEFAULT_LENSES, DIRECTIONS, MEANS, POSTURES, plan_units,
                                   validate_items)
from ant_pr_review.i18n import T
from ant_pr_review.intake import (ask_card, ask_means, ask_posture, build_intake_from_args,
                                  means_of, posture_of, run_intake_interactive)
from ant_pr_review.jsonio import read_json, write_json
from ant_pr_review.plans import run_plans
from ant_pr_review.reaudit import run_reaudit
from ant_pr_review.report import checklist_lines
from ant_pr_review.roster import slug
from ant_pr_review.store import DEFAULT_THRESHOLDS
from ant_pr_review.ui import ScriptedIO
from helpers import M1, M2, M3, ScriptBackend, auto_review, make_run, ok, review_data

t = T("en")
Q = lambda *_: None
# org, parties, jurisdictions, channels, stakeholders, publish_at, keywords, embargo,
# speaker, background, locked (lines, then /done), focus
FILL = ["Acme", "Beta Corp", "", "1", "", "", "2027-01-05", "phones", "",
        "PR lead", "Recall last week", "我們很抱歉，造成不便。", "Second, with a comma.", "/done",
        "tone"]
TEXT = "# 標題\n\n我們的產品很棒棒，大家都喜翻。\n\nA公司的手機曾經爆炸。 Second sentence."
RISK = {"id": "R01", "anchor": "D1.P03.S1", "dimension": "provability", "scope": "tw",
        "scenario": "s", "standard": "std", "mitigation": "m", "score": 12}
KIT = {"holding_statement": "We are looking into it.", "qa": [], "monitoring_keywords": [],
       "escalation": [], "do_not_say": []}
B_OUT = {"recommendation": "publish_revised", "headline_options": [], "paragraphs": [],
         "alternative": "", "notes": ""}
RR = {"verdicts": [{"issue": "R01", "verdict": "FULLY", "note": ""}]}


def step(day, time, action, cat, **kw):
    return dict({"day": day, "time": time, "action": action, "category": cat, "channel": "web",
                 "notes": "n", "trigger": "", "stop": ""}, **kw)


def excl(tactic, exposure="Journalists and platform reports.", alt="Name the spokesperson."):
    return {"tactic": tactic, "why": "deceives readers", "law": "Fair Trade Act",
            "exposure": exposure, "watch_for": "a sudden wave of new accounts",
            "lawful_alternative": alt}


def labels(*cats, flags=()):
    return {"labels": [{"step": n, "category": c, "reason": f"r{n}"}
                       for n, c in enumerate(cats, 1)],
            "excluded_flags": [{"entry": e, "problem": p} for e, p in flags]}


def setup(tmp_path, direction="outbound", models=(M1, M2), card=None, intake_extra=None):
    run = make_run(tmp_path, text=TEXT, direction=direction, models=models, card=card)
    if intake_extra:
        it = read_json(run.path("00-intake.json"))
        it.update(intake_extra)
        write_json(run.path("00-intake.json"), it)
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


def tl(*steps, excluded=()):
    return {"steps": list(steps), "excluded": list(excluded)}


# ---- intake --------------------------------------------------------------------------

# @S-context-card-010
def test_posture_radio_and_means_checkbox_defaults():
    assert ask_posture(ScriptedIO([""]), t) == "clarify_apologize"
    assert ask_means(ScriptedIO([""]), t) == ["white", "gray", "black"]
    io = ScriptedIO(["1 2 3", "", "1", ""])
    assert ask_means(io, t) == ["white"] and "Choose at least 1" in io.text
    it = run_intake_interactive(ScriptedIO(["", "", "", "2", "", "some text", "/done"]
                                           + FILL + [""]),
                                t, "en")
    assert it["posture"] == "promote" and it["means"] == ["white", "gray", "black"]


# @S-context-card-011
def test_posture_and_means_from_arguments():
    it = build_intake_from_args("outbound", ["x"], lang="en", posture="expose",
                                means="white,gray")
    assert it["posture"] == "expose" and it["means"] == ["white", "gray"]
    it = build_intake_from_args("outbound", ["x"], lang="en")
    assert it["posture"] == "clarify_apologize" and it["means"] == ["white", "gray", "black"]
    with pytest.raises(ValueError, match="clarify_apologize"):
        build_intake_from_args("outbound", ["x"], lang="en", posture="smear")
    with pytest.raises(ValueError, match="white"):
        build_intake_from_args("outbound", ["x"], lang="en", means="red")


# @S-context-card-012
def test_audit_questions_in_card():
    io = ScriptedIO(FILL + [""])
    card = ask_card(io, t, "outbound")
    assert card["speaker"] == "PR lead" and card["background"] == "Recall last week"
    assert card["locked"] == ["我們很抱歉，造成不便。", "Second, with a comma."]
    assert card["focus"] == "tone"
    assert "Recall last week" in io.text and "Second, with a comma." in io.text
    it = build_intake_from_args("outbound", ["x"], lang="en", locked=["A, B and C."],
                                speaker="CEO", background="bg", focus="legal")
    assert it["card"]["locked"] == ["A, B and C."] and it["card"]["speaker"] == "CEO"


# @S-context-card-013
def test_old_intake_reads_as_clarify_and_all_means(tmp_path):
    assert posture_of({}) == "clarify_apologize" and means_of({}) == ["white", "gray", "black"]
    assert [posture_of({"posture": p}) for p in ("clarify", "apologize", "attack", "defend")] \
        == ["clarify_apologize", "clarify_apologize", "expose", "rebut"]
    assert plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw"], "quick") == \
        plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw"], "quick",
                   posture="clarify_apologize")
    run = setup(tmp_path)
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white")),
                 (M2, "classify_means"): labels("white")})
    run_plans(run, b, [M1, M2], "en", say=Q)
    p = next(c["prompt"] for c in b.calls if c["task"] == "timeline")
    assert "Posture: clarify_apologize" in p and "Means in scope: white, gray, black" in p


# ---- checklist -----------------------------------------------------------------------

def _items(direction, posture, lenses=None):
    units = plan_units(direction, lenses or DEFAULT_LENSES[direction], ["tw"], "quick",
                       posture=posture)
    return {i for u in units for i in u["items"]}


# @S-checklist-008
def test_posture_items_only_under_their_posture():
    ca = _items("outbound", "clarify_apologize")
    assert {"CLR-01", "CLR-02", "APO-01", "APO-02"} <= ca
    assert not {i for i in ca if i[:3] in ("PRO", "EXP", "RBT")}
    exp = _items("outbound", "expose")
    assert {"EXP-01", "EXP-02", "EXP-03"} <= exp and not {i for i in exp if i[:3] in ("CLR", "APO")}
    unit = plan_units("outbound", ["legal"], ["tw"], "quick", posture="expose")[0]
    p = prompts.review_prompt({"direction": "outbound", "posture": "attack", "card": {}},
                              unit, "x")
    assert "Posture: expose" in p


# @S-checklist-009
def test_every_posture_in_every_direction():
    prefix = {"clarify_apologize": "CLR", "promote": "PRO", "expose": "EXP", "rebut": "RBT"}
    for d in DIRECTIONS:
        for p in POSTURES:
            assert any(i.startswith(prefix[p]) for i in _items(d, p)), (d, p)
    with pytest.raises(ValueError, match="posture"):
        plan_units("outbound", ["legal"], ["tw"], "quick", posture="smear")
    bad = [{"id": "X-01", "lens": "legal", "directions": ["outbound"], "dimension": "legal",
            "postures": ["smear"], "text": "?"}]
    with pytest.raises(ValueError, match="posture"):
        validate_items(bad)
    assert MEANS == ["white", "gray", "black"]


# @S-checklist-010
def test_ticked_means_never_narrow_the_review():
    intake = {"direction": "outbound", "posture": "clarify_apologize", "means": ["white"],
              "card": {}}
    unit = plan_units("outbound", ["legal"], ["tw"], "quick")[0]
    p = prompts.review_prompt(intake, unit, "x")
    assert "white, gray and black angles" in p and "Means in scope" not in p
    assert "- black:" in p
    tp = prompts.timeline_prompt([], "x", intake)
    assert "Means in scope: white" in tp and "- black:" not in tp


# ---- timeline ------------------------------------------------------------------------

# @S-plans-012
def test_timeline_sorted_numbered_from_publish_date(tmp_path):
    run = setup(tmp_path, card={"publish_at": "2026-11-02"})
    steps = [step(3, "10:00", "Exclusive interview", "gray"), step(0, "09:00", "Publish", "white"),
             step(-1, "15:00", "Brief staff", "white")]
    b = backend({(M1, "timeline"): tl(*steps),
                 (M2, "classify_means"): labels("gray", "white", "white")})
    run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert [(s["n"], s["action"], s["date"]) for s in data["steps"]] == [
        (1, "Brief staff", "2026-11-01"), (2, "Publish", "2026-11-02"),
        (3, "Exclusive interview", "2026-11-05")]
    md = run.path("09-plans/T.md").read_text()
    assert md.index("T-1d") < md.index("T0") < md.index("T+3d")
    assert "2026-11-05 10:00" in md and "gray" in md


# @S-plans-013 @N-plans-002
def test_stricter_label_wins_and_black_never_scheduled(tmp_path):
    run = setup(tmp_path)
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Press release", "white"),
                                      step(1, "09:00", "Community push", "white"),
                                      step(2, "09:00", "Q&A session", "white")),
                 (M2, "classify_means"): labels("gray", "black", "white")})
    run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert [(s["action"], s["category"]) for s in data["steps"]] == [
        ("Press release", "gray"), ("Q&A session", "white")]
    assert [e["tactic"] for e in data["excluded"]] == ["Community push"]
    md = run.path("09-plans/T.md").read_text()
    table = md.split("## ")[1]
    assert "Community push" not in table


# @S-plans-013
def test_unknown_label_is_black_and_unlabelled_step_is_not_scheduled(tmp_path):
    run = setup(tmp_path)
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "A", "purple"), step(1, "09:00", "B", "white")),
                 (M2, "classify_means"): {"labels": [{"step": 1, "category": "white",
                                                      "reason": ""}], "excluded_flags": []}})
    run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert data["steps"] == [] and [e["tactic"] for e in data["excluded"]] == ["A"]
    assert [(d["action"], d["reason"]) for d in data["dropped"]] == [("B", "not_reviewed")]


# @S-plans-014 @N-plans-002
def test_step_outside_ticked_means_is_dropped(tmp_path):
    run = setup(tmp_path, intake_extra={"means": ["white"]})
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white"),
                                      step(1, "10:00", "Exclusive to one outlet", "gray")),
                 (M2, "classify_means"): labels("white", "gray")})
    run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert [s["category"] for s in data["steps"]] == ["white"]
    assert [d["action"] for d in data["dropped"]] == ["Exclusive to one outlet"]
    md = run.path("09-plans/T.md").read_text()
    assert "Exclusive to one outlet" in md and "outside the chosen means" in md


# @S-plans-015
def test_excluded_table_only_with_black_and_scanned_for_evasion(tmp_path):
    entries = [excl("sockpuppet accounts"),
               excl("seeded posts", exposure="Rotate IP addresses to avoid being traced.")]
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white"), excluded=entries),
                 (M2, "classify_means"): labels("white")})
    run = setup(tmp_path / "a")
    run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert data["excluded"][0]["tactic"] == "sockpuppet accounts"
    assert data["excluded"][0]["exposure"] == "Journalists and platform reports."
    assert "[removed by ethics guard: evasion]" in data["excluded"][1]["exposure"]
    assert "Rotate IP" not in run.path("09-plans/T.md").read_text()
    run = setup(tmp_path / "b", intake_extra={"means": ["white", "gray"]})
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white"), excluded=entries),
                 (M2, "classify_means"): labels("white")})
    run_plans(run, b, [M1, M2], "en", say=Q)
    assert read_json(run.path("09-plans/T.json"))["excluded"] == []
    assert "sockpuppet" not in run.path("09-plans/T.md").read_text()
    assert not any("sockpuppet" in c["prompt"] for c in b.calls if c["task"] == "classify_means")


# @S-plans-016
def test_persona_step_sent_back_then_removed(tmp_path):
    run = setup(tmp_path)
    bad = tl(step(1, "10:00", "Seed comments from alt accounts", "white"))
    b = backend({(M1, "timeline"): bad, (M2, "classify_means"): labels("white")})
    run_plans(run, b, [M1, M2], "en", say=Q)
    calls = [c for c in b.calls if c["task"] == "timeline"]
    assert len(calls) == 2 and "ethics guard" in calls[1]["prompt"]
    md = run.path("09-plans/T.md").read_text()
    assert "alt accounts" not in md
    data = read_json(run.path("09-plans/T.json"))
    assert data["steps"] == []
    assert [d["reason"] for d in data["dropped"]] == ["ethics_guard"]


# @S-plans-017
def test_step_on_sensitive_date_is_warned(tmp_path):
    run = setup(tmp_path, card={"publish_at": "2027-02-26"})
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white"),
                                      step(1, "09:00", "Eve post", "white"),
                                      step(2, "09:00", "Follow-up post", "white")),
                 (M2, "classify_means"): labels("white", "white", "white")})
    run_plans(run, b, [M1, M2], "en", say=Q)
    steps = read_json(run.path("09-plans/T.json"))["steps"]
    assert steps[0]["warnings"] == []
    assert all(any("228 Peace Memorial Day" in w for w in s["warnings"]) for s in steps[1:])
    p = next(c["prompt"] for c in b.calls if c["task"] == "classify_means")
    assert '"day": 2' in p and '"time": "09:00"' in p


# @S-plans-018
def test_plan_a_never_changes_a_locked_sentence(tmp_path):
    run = setup(tmp_path, card={"locked": ["我們的產品很棒棒，大家都喜翻。"]})
    out = run_plans(run, backend(), [M1, M2], "en", say=Q)
    assert "我們的產品很棒棒，大家都喜翻。" in run.path("09-plans/A.md").read_text()
    assert any("D1.P02" in w and "locked" in w for w in out["warnings"])


# @S-plans-018
def test_locked_sentence_kept_when_a_neighbour_sentence_changes(tmp_path):
    run = setup(tmp_path, card={"locked": ["A公司的手機曾經爆炸。"]})
    b = backend({(M1, "plan_a"): {"paragraphs": [{"id": "D1.P03.S2", "text": "Changed."}],
                                  "corrections": []}})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    a = run.path("09-plans/A.md").read_text()
    assert "A公司的手機曾經爆炸。" in a and "Changed." in a
    assert not any("locked" in w for w in out["warnings"])


# ---- stage reviews -------------------------------------------------------------------

# @S-plans-021
def test_every_stage_reviewed_by_another_vendor(tmp_path):
    run = setup(tmp_path)
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white"),
                                      excluded=[excl("fake reviews")]),
                 (M2, "classify_means"): labels("white")})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    reviewed = [(c["model"], c["task"]) for c in b.calls if c["model"] == M2]
    assert reviewed.count((M2, "rereview")) == 3 and (M2, "classify_means") in reviewed
    stages = {s["stage"]: s for s in out["stages"]}
    assert set(stages) == {"A", "B", "C", "T", "X"}
    assert all(s["writer"] == M1 and s["reviewer"] == M2 and s["status"] == "ok"
               for s in stages.values())


# @S-plans-022
def test_operational_excluded_entry_is_withheld(tmp_path):
    run = setup(tmp_path)
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white"),
                                      excluded=[excl("fake reviews"),
                                                excl("paid posters", exposure="Step 1 ...")]),
                 (M2, "classify_means"): labels("white", flags=[(2, "reads as instructions")])})
    run_plans(run, b, [M1, M2], "en", say=Q)
    ex = read_json(run.path("09-plans/T.json"))["excluded"]
    assert ex[0]["exposure"] == "Journalists and platform reports."
    assert ex[1]["tactic"] == "paid posters" and ex[1]["law"] == "Fair Trade Act"
    assert ex[1]["lawful_alternative"] == "Name the spokesperson."
    assert "Step 1" not in ex[1]["exposure"] and "reads as instructions" in ex[1]["exposure"]
    assert "a sudden wave" not in ex[1]["watch_for"]


# @S-plans-023
def test_failed_stage_review_shown_as_not_reviewed(tmp_path):
    run = setup(tmp_path)
    n = {"k": 0}

    def rr(prompt):
        n["k"] += 1
        return BackendError("slow", reason="timeout") if "looking into it" in prompt else RR
    b = backend({("*", "rereview"): rr})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    c = next(s for s in out["stages"] if s["stage"] == "C")
    assert c["status"] == "failed" and c["reason"] == "timeout"
    from ant_pr_review.report import stage_lines
    lines = "\n".join(stage_lines(t, out["stages"]))
    assert "not reviewed" in lines and "timeout" in lines


# ---- re-audit ------------------------------------------------------------------------

def _hashes(run):
    return {str(p.relative_to(run.root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in run.path("04-reviews").rglob("*.json")}


# @S-plans-019
def test_revision_reaudited_at_quick_depth(tmp_path):
    run = setup(tmp_path)
    run_plans(run, backend(), [M1, M2], "en", say=Q)
    before = _hashes(run)
    b = ScriptBackend({("*", "review"): auto_review()})
    st = run_reaudit(run, b, [M1, M2], "en", DEFAULT_THRESHOLDS, say=Q)
    assert st["status"] == "done"
    units = [u["id"] for u in plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw"], "quick")]
    assert sorted((c["model"], c["task"]) for c in b.calls) == sorted(
        (m, "review") for m in (M1, M2) for _ in units)
    assert all("很棒，大家都喜歡" in c["prompt"] for c in b.calls)
    syn = read_json(run.path("09-plans/reaudit/06-synthesis.json"))
    assert syn["consolidated"]["provisional"] is True
    assert _hashes(run) == before


# @S-plans-020
def test_no_reaudit_without_a_revision(tmp_path):
    run = setup(tmp_path / "u")
    run_plans(run, backend({(M1, "plan_a"): {"paragraphs": [], "corrections": []}}), [M1, M2],
              "en", say=Q)
    b = ScriptBackend({("*", "review"): auto_review()})
    assert run_reaudit(run, b, [M1, M2], "en", DEFAULT_THRESHOLDS, say=Q)["status"] == "unchanged"
    run = setup(tmp_path / "i", direction="inbound")
    assert run_reaudit(run, b, [M1, M2], "en", DEFAULT_THRESHOLDS,
                       say=Q)["status"] == "not_applicable"
    assert b.calls == []


# ---- report --------------------------------------------------------------------------

def _item(item, unit, by_model, unanswered=(), verdict=None):
    rank = {"na": 0, "pass": 1, "concern": 2, "fail": 3}
    v = verdict or max(by_model.values(), key=rank.get)
    return {"item": item, "unit": unit, "verdict": v, "label": "", "by_model": by_model,
            "unanswered": list(unanswered), "score": 0}


# @S-review-matrix-024
def test_checklist_is_checkbox_list_with_bars_and_marks():
    items = [_item("LEG-01", "tw.all", {M1: "pass", M2: "pass", M3: "concern"}),
             _item("JOU-01", "global.all", {M1: "na", M2: "pass", M3: "pass"}),
             _item("SOC-01", "tw.all", {M1: "pass", M2: "pass"}, unanswered=[M3]),
             _item("LEG-02", "tw.all", {M1: "na", M2: "na", M3: "na"})]
    lines = checklist_lines(t, items, [M1, M2, M3])
    first = next(ln for ln in lines if "LEG-01" in ln)
    assert first.startswith("- [ ]") and "███████░░░  67%  2/3 ⚠" in first
    assert f"{M3} ⚠" in first and f"{M1} ✓" in first
    third = next(ln for ln in lines if "SOC-01" in ln)
    assert third.startswith("- [ ]") and "██████████ 100%  2/2 ✓" in third
    second = next(ln for ln in lines if "JOU-01" in ln)
    assert second.startswith("- [x]") and "██████████ 100%  2/2 ✓" in second
    assert "1 unanswered" in third and f"{M3} ∅" in third
    na = next(ln for ln in lines if "LEG-02" in ln)
    assert na.startswith("- [x]") and "n/a" in na
    text = "\n".join(lines)
    assert "legal" in text and "global" in text
    overall = next(ln for ln in lines if "Overall" in ln)
    assert "6/7" in overall and "86%" in overall


# @S-review-matrix-025
def test_report_carries_revision_reaudit_and_timeline(tmp_path, monkeypatch):
    import ant_pr_review.cli as cli
    from ant_pr_review.backends.fake import FakeBackend
    from ant_pr_review.store import Store
    from ant_pr_review.workspace import PHASES, list_runs
    assert PHASES.index("plans") < PHASES.index("reaudit") < PHASES.index("report")
    monkeypatch.setattr(cli, "get_backend", lambda name: FakeBackend())
    store = Store(tmp_path / "home")
    code = cli.main(["new", "--yes", "--backend", "fake", "--target",
                     "# Post\n\nOur product is great.\n\nBuy now."], io=ScriptedIO(), store=store)
    assert code == 3
    run = list_runs(store.runs_dir)[-1]
    md = run.path("08-report.v1.md").read_text()
    for heading in ("Revision (plan A)", "Revised full text", "Re-audit of the revision",
                    "Timeline of means", "Assessed, not scheduled", "Stage reviews"):
        assert f"## {heading}" in md or f"### {heading}" in md, heading
    assert "@@ D1." in md and "→" in md and "- [" in md


# ---- review findings (tier 3) ----------------------------------------------------------

# @S-plans-024
def test_duplicate_reviewer_labels_keep_the_strictest(tmp_path):
    run = setup(tmp_path)
    lab = {"labels": [{"step": 1, "category": "black", "reason": "persona"},
                      {"step": 1, "category": "white", "reason": "fine"}], "excluded_flags": []}
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Sock push", "white")),
                 (M2, "classify_means"): lab})
    run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert data["steps"] == [] and [e["tactic"] for e in data["excluded"]] == ["Sock push"]


# @S-plans-025
@pytest.mark.parametrize("answer", [BackendError("down", reason="offline"),
                                    {"labels": [], "excluded_flags": []}])
def test_unreviewed_excluded_table_is_withheld(tmp_path, answer):
    run = setup(tmp_path)
    if isinstance(answer, dict):
        from ant_pr_review.backends.base import Result
        answer = Result(model=M2, model_id="x", data=None, refused=True)
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white"),
                                      excluded=[excl("paid posters",
                                                     exposure="Detected by IP overlap.")]),
                 (M2, "classify_means"): answer})
    run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert data["steps"] == []
    ex = data["excluded"][0]
    assert ex["tactic"] == "paid posters" and "IP overlap" not in ex["exposure"]
    assert "a sudden wave" not in ex["watch_for"]
    assert "IP overlap" not in run.path("09-plans/T.md").read_text()


# @S-plans-026
def test_reviewer_text_is_scanned_and_persona_names_survive_rendering(tmp_path):
    run = setup(tmp_path)
    lab = {"labels": [{"step": 1, "category": "black",
                       "reason": "Rotate IP addresses to avoid being traced."}],
           "excluded_flags": []}
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Seed praise", "white"),
                                      excluded=[excl("A sockpuppet network posting praise")]),
                 (M2, "classify_means"): lab})
    run_plans(run, b, [M1, M2], "en", say=Q)
    md = run.path("09-plans/T.md").read_text()
    assert "Rotate IP" not in md and "Rotate IP" not in run.path("09-plans/T.json").read_text()
    assert "A sockpuppet network posting praise" in md


# @S-plans-027
def test_steps_beyond_the_cap_are_disclosed_and_stop_is_reviewed(tmp_path):
    from ant_pr_review.timeline import MAX_STEPS
    run = setup(tmp_path)
    steps = [step(0, "09:00", f"S{n}", "white", stop=f"stop{n}") for n in range(MAX_STEPS + 2)]
    b = backend({(M1, "timeline"): tl(*steps),
                 (M2, "classify_means"): labels(*["white"] * (MAX_STEPS + 2))})
    run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert len(data["steps"]) == MAX_STEPS
    assert [(d["action"], d["reason"]) for d in data["dropped"]] == [
        (f"S{MAX_STEPS}", "too_many"), (f"S{MAX_STEPS + 1}", "too_many")]
    p = next(c["prompt"] for c in b.calls if c["task"] == "classify_means")
    assert "stop0" in p


# @S-plans-028
def test_unreadable_publish_date_is_disclosed(tmp_path):
    run = setup(tmp_path, card={"publish_at": "next Friday"})
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white")),
                 (M2, "classify_means"): labels("white")})
    run_plans(run, b, [M1, M2], "en", say=Q)
    assert "next Friday" in run.path("09-plans/T.md").read_text()
    assert read_json(run.path("09-plans/T.json"))["t0_invalid"] is True


# @S-plans-018
def test_a_lock_not_found_in_the_text_is_warned(tmp_path):
    run = setup(tmp_path, card={"locked": ["This sentence is not in the text."]})
    out = run_plans(run, backend(), [M1, M2], "en", say=Q)
    assert any("not found" in w and "This sentence" in w for w in out["warnings"])


# @S-plans-019
def test_reaudit_reruns_when_posture_or_matrix_change(tmp_path):
    run = setup(tmp_path)
    run_plans(run, backend(), [M1, M2], "en", say=Q)
    run_reaudit(run, ScriptBackend({("*", "review"): auto_review()}), [M1, M2], "en",
                DEFAULT_THRESHOLDS, say=Q)
    it = read_json(run.path("00-intake.json"))
    it["posture"] = "expose"
    write_json(run.path("00-intake.json"), it)
    b = ScriptBackend({("*", "review"): auto_review()})
    run_reaudit(run, b, [M1, M2], "en", DEFAULT_THRESHOLDS, say=Q)
    assert b.calls and all("Posture: expose" in c["prompt"] for c in b.calls)


# @S-review-matrix-026
def test_a_reviewer_whose_unit_failed_is_never_a_tick():
    items = [_item("JOU-01", "global.all", {M1: "pass"}),
             _item("JOU-02", "global.all", {}, verdict="na")]
    lines = checklist_lines(t, items, [M1, M2])
    first = next(ln for ln in lines if "JOU-01" in ln)
    assert first.startswith("- [ ]") and f"{M2} ∅" in first and "1 unanswered" in first
    assert next(ln for ln in lines if "JOU-02" in ln).startswith("- [ ]")


# @S-review-matrix-025
def test_report_survives_missing_plan_files(tmp_path):
    from ant_pr_review.report import _plans_sections
    run = setup(tmp_path)
    run_plans(run, backend(), [M1, M2], "en", say=Q)
    write_json(run.path("09-plans/reaudit/status.json"), {"status": "done"})
    run.path("09-plans/A.md").unlink()
    text = "\n".join(_plans_sections(t, run, None))
    assert "Revision (plan A)" in text


# @S-run-workspace-007
def test_a_run_finished_before_the_reorder_stays_done(tmp_path):
    from ant_pr_review.workspace import PHASE_INPUTS, PHASES
    run = setup(tmp_path)
    st = read_json(run.state_path)
    old_inputs = {"plans": ["06-synthesis.json", "01-sources/segments.json"],
                  "report": ["06-synthesis.json", "07-jmerge"]}
    for ph in PHASES:
        if ph == "reaudit":
            st["phases"].pop(ph, None)
            continue
        rels = old_inputs.get(ph, PHASE_INPUTS[ph])
        hashes = {}
        from ant_pr_review.workspace import _hash_input
        for r in rels:
            hashes.update(_hash_input(run.root, r))
        st["phases"][ph] = {"status": "done", "inputs": hashes}
    st["version"] = 1
    write_json(run.state_path, st)
    assert run.refresh() == [] and run.first_incomplete() is None


# @S-plans-024
@pytest.mark.parametrize("numbers", [(0, 1, 2), (1, 2, 4)])
def test_misnumbered_labels_count_as_not_reviewed(tmp_path, numbers):
    run = setup(tmp_path)
    lab = {"labels": [{"step": n, "category": c, "reason": ""}
                      for n, c in zip(numbers, ("white", "black", "white"))],
           "excluded_flags": []}
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Press release", "white"),
                                      step(1, "09:00", "Paid posters praising us", "white"),
                                      step(2, "09:00", "Q&A", "white")),
                 (M2, "classify_means"): lab})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert data["steps"] == []
    assert {d["reason"] for d in data["dropped"]} == {"not_reviewed"}
    assert next(s for s in out["stages"] if s["stage"] == "T")["status"] == "invalid"


# @S-plans-018
def test_a_locked_denial_survives_the_guard(tmp_path):
    from ant_pr_review import ethics
    assert ethics.scan_text("我們從未僱用網軍。") == []
    run = make_run(tmp_path, text="# T\n\n我們沒有僱用網軍。產品很棒棒。", card={
        "locked": ["我們沒有僱用網軍。"]})
    for m in (M1, M2):
        write_json(run.path(f"04-reviews/tw.all/{slug(m)}.json"), ok(m, "tw.all", review_data()))
    write_json(run.path("06-synthesis.json"), {"risks": [RISK], "unverified": [],
                                               "jurisdictions": {}})
    b = backend({(M1, "plan_a"): {"paragraphs": [{"id": "D1.P02",
                                                  "text": "我們沒有僱用網軍。產品很棒。"}],
                                  "corrections": []}})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    a = run.path("09-plans/A.md").read_text()
    assert "我們沒有僱用網軍。" in a and "removed by ethics guard" not in a
    assert "產品很棒。" in a


# @S-plans-018
def test_a_lock_wrapped_in_other_words_is_not_kept(tmp_path):
    run = make_run(tmp_path, text="# T\n\nThe recall is voluntary. We acted early.",
                   card={"locked": ["The recall is voluntary."]})
    for m in (M1, M2):
        write_json(run.path(f"04-reviews/tw.all/{slug(m)}.json"), ok(m, "tw.all", review_data()))
    write_json(run.path("06-synthesis.json"), {"risks": [RISK], "unverified": [],
                                               "jurisdictions": {}})
    b = backend({(M1, "plan_a"): {"paragraphs": [
        {"id": "D1.P02", "text": 'Regulators dispute that "The recall is voluntary." We acted early.'},
        {"id": "D1.P02+", "text": "Correction: the recall was ordered."}], "corrections": []}})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    a = run.path("09-plans/A.md").read_text()
    assert "Regulators dispute" not in a
    assert any("D1.P02" in w and "locked" in w for w in out["warnings"])
    assert any("inserted" in w and "locked" in w for w in out["warnings"])


# @S-plans-021
def test_stage_bookkeeping_and_reviewer_reason_scanned(tmp_path):
    run = setup(tmp_path)
    lab = {"labels": [{"step": 1, "category": "white",
                       "reason": "Rotate IP addresses to avoid being traced."}],
           "excluded_flags": []}
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Exclusive", "gray")),
                 (M2, "classify_means"): lab})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    data = read_json(run.path("09-plans/T.json"))
    assert data["steps"][0]["category"] == "gray"
    assert "relabelled" not in run.path("09-plans/T.md").read_text()
    assert "Rotate IP" not in run.path("09-plans/T.json").read_text()
    tstage = next(s for s in out["stages"] if s["stage"] == "T")
    assert tstage["result"].startswith("0 relabelled")
    run = setup(tmp_path / "f")
    b = backend({(M1, "timeline"): tl(step(0, "09:00", "Publish", "white"),
                                      excluded=[excl("paid posters")]),
                 (M2, "classify_means"): BackendError("down", reason="offline")})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    assert next(s for s in out["stages"] if s["stage"] == "X")["result"].startswith("1 ")


# @S-plans-014
def test_black_only_means_asks_for_no_steps(tmp_path):
    run = setup(tmp_path, intake_extra={"means": ["black"]})
    b = backend({(M1, "timeline"): tl(excluded=[excl("paid posters")]),
                 (M2, "classify_means"): labels()})
    run_plans(run, b, [M1, M2], "en", say=Q)
    sys_ = next(c["system"] for c in b.calls if c["task"] == "timeline")
    assert "Schedule no steps" in sys_ and "Use only the means in scope" not in sys_


# @S-plans-018
def test_redaction_never_takes_a_locked_sentence_with_it(tmp_path):
    run = make_run(tmp_path, text="# T\n\n我們沒有僱用網軍。產品很棒棒。", card={
        "locked": ["我們沒有僱用網軍。"]})
    for m in (M1, M2):
        write_json(run.path(f"04-reviews/tw.all/{slug(m)}.json"), ok(m, "tw.all", review_data()))
    write_json(run.path("06-synthesis.json"), {"risks": [RISK], "unverified": [],
                                               "jurisdictions": {}})
    b = backend({(M1, "plan_a"): {"paragraphs": [{"id": "D1.P02",
                                                  "text": "我們沒有僱用網軍。請用小帳幫忙宣傳網軍。"}],
                                  "corrections": []}})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    a = run.path("09-plans/A.md").read_text()
    assert "我們沒有僱用網軍。" in a and "小帳" not in a
    assert any("locked" in w for w in out["warnings"])
