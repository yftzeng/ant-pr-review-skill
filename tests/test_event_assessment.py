"""The event assessment: grade, risk outlook, action, activation (D-0006)."""
import pytest

from ant_pr_review import grading, plans, prompts, timeline
from ant_pr_review.i18n import T
from ant_pr_review.intake import build_intake_from_args, run_intake_interactive
from ant_pr_review.jsonio import read_json, write_json
from ant_pr_review.refresh import compute_synthesis
from ant_pr_review.report import write_report
from ant_pr_review.review import run_round1
from ant_pr_review.store import DEFAULT_THRESHOLDS
from ant_pr_review.ui import ScriptedIO
from helpers import M1, M2, ScriptBackend, auto_review, make_run

t = T("en")
CLEAR = {"jurisdictions": {"tw": {"red_lines": {"election_law": {"status": "clear"}}}}}
RED = {"jurisdictions": {"tw": {"red_lines": {"election_law": {"status": "confirmed"}}}}}


def intake(signals=(), characterised=False, **kw):
    return {"direction": "outbound", "card": {"signals": list(signals),
                                              "characterised": characterised}, **kw}


# @S-review-matrix-031
def test_grade_the_higher_wins_and_red_lines_first():
    a = grading.assess(intake(["platform_trending", "multi_media"]), CLEAR)
    assert a["grade"] == "II" and a["owner"] == "executives" and a["activation"] == "activate"
    assert a["basis"] == ["platform_trending", "multi_media"] and a["override"] == []
    a = grading.assess(intake(["platform_trending", "multi_media", "scattered_reviews"]), CLEAR)
    assert a["grade"] == "II"
    a = grading.assess(intake(["scattered_reviews", "major_safety"]), CLEAR)
    assert a["grade"] == "I" and a["override"] == ["major_safety"] and a["owner"] == "top_and_advisers"
    a = grading.assess(intake(["small_spread"]), RED)
    assert a["grade"] == "I" and a["override"] == ["red_line:election_law"]
    a = grading.assess(intake(["self_media"]), CLEAR)
    assert a["grade"] == "III" and a["activation"] == "standby" and a["owner"] == "management"
    a = grading.assess(intake(["small_spread"]), CLEAR)
    assert a["grade"] == "IV" and a["activation"] == "observe" and a["owner"] == "business_unit"
    a = grading.assess(intake(), CLEAR)
    assert a["grade"] is None and a["activation"] == "manual"
    # a drafting tier-4 flag for injury, a crime or minors is a bottom line; a lawsuit is not
    d = dict(intake(["small_spread"]), purpose="drafting",
             brief={"tier4": ["lawsuit"], "characterised": True})
    assert grading.assess(d, CLEAR)["grade"] == "IV"
    d["brief"]["tier4"] = ["injury"]
    a = grading.assess(d, CLEAR)
    assert a["grade"] == "I" and a["override"] == ["tier4:injury"] and a["characterised"] is False  # tier 4: holding only
    # an old card with no signals reads as ungraded, not characterised
    a = grading.assess({"direction": "outbound", "card": {}}, CLEAR)
    assert a["grade"] is None and a["characterised"] is False


def report_run(tmp_path, card):
    run = make_run(tmp_path, card=card)
    run_round1(run, ScriptBackend({("*", "review"): auto_review()}), [M1, M2], "en",
               say=lambda *_: None)
    write_report(run, compute_synthesis(run, [M1, M2], DEFAULT_THRESHOLDS), lang="en")
    return run.path("08-report.v1.md").read_text(encoding="utf-8")


def test_report_opens_with_the_event_assessment(tmp_path):
    md = report_run(tmp_path, {"signals": ["platform_trending", "multi_media"]})
    sec = md.split(f"## {t('report.event')}", 1)[1].split("\n## ", 1)[0]
    assert md.index(t("report.event")) < md.index(t("report.verdict_title"))
    for needle in (t("grade.II"), t("owner.executives"), t("signal.platform_trending"),
                   t("activation.activate"), t("report.event.outlook"),
                   t("report.event.action"), t("report.event.facts"),
                   t("axis.predictability")):
        assert needle in sec, needle
    md = report_run(tmp_path / "b", {})
    sec = md.split(f"## {t('report.event')}", 1)[1].split("\n## ", 1)[0]
    assert t("grade.none") in sec and t("activation.manual") in sec


# @S-review-matrix-032
def test_checklist_subtotals_by_control_axis(tmp_path):
    from ant_pr_review.catalog import AXES, item_index
    idx = item_index()
    assert set(AXES) == {"predictability", "explicability", "influence"}
    assert all(i in idx for items in AXES.values() for i in items)
    md = report_run(tmp_path, {})
    subtotals = md.split(t("report.subtotals"), 1)[1]
    for ax in AXES:
        assert t(f"axis.{ax}") in subtotals


# @S-context-card-018
def test_card_signals_and_characterised():
    i = build_intake_from_args("outbound", ["x"], lang="en",
                               signals="platform_trending,major_safety", characterised=True)
    assert i["card"]["signals"] == ["platform_trending", "major_safety"]
    assert i["card"]["characterised"] is True
    i = build_intake_from_args("outbound", ["x"], lang="en")
    assert i["card"]["signals"] == [] and i["card"]["characterised"] is False
    with pytest.raises(ValueError, match="platform_trending"):
        build_intake_from_args("outbound", ["x"], lang="en", signals="viral")
    from test_context_card import FILL
    io = ScriptedIO(["", "", "", "", "", "", "Some text", "/done"] + FILL + [""])
    card = run_intake_interactive(io, t, "en")["card"]
    assert card["signals"] == [] and card["characterised"] is False
    assert t("card.signals") in io.text and t("card.characterised") in io.text


# @S-plans-038
def test_kit_formal_statement_only_when_characterised():
    data = {"holding_statement": "h", "formal_statement": "f", "qa": [],
            "monitoring_keywords": [], "escalation": [], "do_not_say": []}
    assert plans.kit_shape(dict(data), False)["formal_statement"] == ""
    assert plans.kit_shape(dict(data), True)["formal_statement"] == "f"
    assert "holding statement only" in prompts.kit_system("en", characterised=False)
    assert "formal statement" in prompts.kit_system("en", characterised=True)
    md = plans.render_kit(t, dict(data))
    assert t("plans.formal") in md
    assert t("plans.formal") not in plans.render_kit(t, dict(data, formal_statement=""))


# @S-plans-039
def test_timeline_attention_stage_and_silence():
    steps = [{"day": 0, "time": "09:00", "action": "Statement", "category": "white",
              "stage": "alarmed", "silence": False},
             {"day": 3, "time": "10:00", "action": "Stop public statements; owners' line open",
              "category": "white", "stage": "decline", "silence": True},
             {"day": 4, "time": "10:00", "action": "Old step", "category": "white"}]
    labels = {n: {"category": "white"} for n in (1, 2, 3)}
    d = timeline.build(steps, labels, [], {}, ["white"], "", ["tw"], "w")
    assert [s["stage"] for s in d["steps"]] == ["alarmed", "decline", ""]
    assert [s["silence"] for s in d["steps"]] == [False, True, False]
    md = timeline.render(t, d)
    assert t("stage.alarmed") in md and t("plans.t.silence") in md
    assert "silence" in prompts.timeline_system("en", ["white"])
    assert "issue-attention" in prompts.timeline_system("en", ["white"])


# edges the first tests left open
def test_assessment_edges():
    pending = {"jurisdictions": {"tw": {"red_lines": {"election_law": {"status": "needs_ruling"}}}}}
    assert grading.assess(intake(["small_spread"]), pending)["grade"] == "IV"
    a = grading.assess(intake(["major_safety", "platform_trending"]), CLEAR)
    assert a["grade"] == "I" and a["basis"] == [] and a["override"] == ["major_safety"]
    d = dict(intake(characterised=True), purpose="drafting", brief={"characterised": False})
    assert grading.assess(d, CLEAR)["characterised"] is False
    from ant_pr_review.report import axis_groups
    from ant_pr_review.catalog import AXES
    items = [{"item": "SOC-07"}, {"item": "JOU-17"}, {"item": "LEG-01"}]
    g = axis_groups(items)
    assert [i["item"] for i in g["predictability"]] == ["SOC-07"]
    assert [i["item"] for i in g["explicability"]] == ["JOU-17"] and g["influence"] == []
    assert "leave formal_statement empty" in prompts.kit_system("en", characterised=False)
    d = timeline.build([{"day": 0, "action": "x", "category": "white", "stage": "bogus"}],
                       {1: {"category": "white"}}, [], {}, ["white"], "", ["tw"], "w")
    assert d["steps"][0]["stage"] == ""


def test_report_names_the_bottom_line(tmp_path):
    md = report_run(tmp_path, {"signals": ["major_safety", "small_spread"]})
    sec = md.split(f"## {t('report.event')}", 1)[1].split("\n## ", 1)[0]
    assert t("grade.I") in sec and t("report.event.bottom", what=t("signal.major_safety")) in sec


def test_drafting_card_does_not_ask_characterised():
    answers = ["2", "", "", "", "",
               "1", "A batch shipped with a faulty seal", "/done", "/done", "/done", "", "", "",
               "buyers", "", "", "", "/done", "/done", "/done", "/done", "legal", "", "/done",
               "", "/done"]
    from test_context_card import FILL
    io = ScriptedIO(answers + FILL[:-4] + [""])  # no characterised, no times
    it = run_intake_interactive(io, t, "en")
    assert t("card.characterised.label") not in io.text and "characterised" not in it["card"]


# ---- from the tier-3 review ----

def test_latent_red_line_in_an_unpublished_text():
    a = grading.assess(intake(), RED)
    assert a["grade"] is None and a["latent"] == ["red_line:election_law"]
    a = grading.assess(dict(intake(), direction="inbound"), RED)
    assert a["grade"] == "I" and a["latent"] == []
    a = grading.assess(intake(["small_spread"]), RED)
    assert a["grade"] == "I" and a["latent"] == []


def test_drafting_tier4_is_never_characterised():
    d = dict(intake(), purpose="drafting", brief={"tier4": ["lawsuit"], "characterised": True})
    assert grading.characterised_of(d) is False
    with pytest.raises(ValueError, match="brief"):
        build_intake_from_args("outbound", [], lang="en", purpose="drafting", characterised=True,
                               brief={"kind": "product", "confirmed": ["x"]})


def test_axis_lines_say_how_many_items_were_asked():
    from ant_pr_review.report import axis_line
    items = [{"item": "JOU-07", "unit": "tw.journalist", "by_model": {"m": "pass"}}]
    line = axis_line(t, "explicability", items)
    assert "1/6" in line and t("axis.explicability") in line


def test_event_section_notes_a_missing_kit_and_the_regrade_path(tmp_path):
    md = report_run(tmp_path, {"signals": ["platform_trending"]})
    sec = md.split(f"## {t('report.event')}", 1)[1].split("\n## ", 1)[0]
    assert t("report.event.no_kit") in sec and "rerun" in sec and "--from report" in sec


def test_drafting_report_header_hides_the_card_line(tmp_path):
    from test_drafting import BRIEF, backend, draft, drafting_run
    run = drafting_run(tmp_path, dict(BRIEF, characterised=True))
    draft(run, backend())
    run_round1(run, ScriptBackend({("*", "review"): auto_review()}), [M1, M2], "en",
               say=lambda *_: None)
    write_report(run, compute_synthesis(run, [M1, M2], DEFAULT_THRESHOLDS), lang="en")
    md = run.path("08-report.v1.md").read_text(encoding="utf-8")
    head = md.split(f"## {t('report.event')}", 1)[0]
    assert t("card.characterised.label") not in head
    assert t("report.event.characterised") in md


def test_kit_says_a_formal_statement_is_withheld():
    data = {"holding_statement": "h", "formal_statement": "f", "qa": [],
            "monitoring_keywords": [], "escalation": [], "do_not_say": []}
    md = plans.render_kit(t, plans.kit_shape(dict(data), False))
    assert t("plans.formal_withheld") in md and "\nf\n" not in md


def test_one_silence_point_and_an_early_one_warned():
    steps = [{"day": 0, "action": "a", "category": "white", "stage": "alarmed", "silence": True},
             {"day": 4, "action": "b", "category": "white", "stage": "decline", "silence": True}]
    d = timeline.build(steps, {1: {"category": "white"}, 2: {"category": "white"}}, [], {},
                       ["white"], "", ["tw"], "w", t=t)
    assert [s["silence"] for s in d["steps"]] == [True, False]
    assert t("plans.t.warn_early_silence") in d["steps"][0]["warnings"]
    assert not d["steps"][1]["warnings"]


def test_plan_c_applies_the_shape(tmp_path):
    kit = {"holding_statement": "Holding words.", "formal_statement": "Formal words.", "qa": [],
           "monitoring_keywords": [], "escalation": [], "do_not_say": []}
    run = make_run(tmp_path)
    b = ScriptBackend({("*", "kit"): dict(kit)})
    text, _ = plans.plan_c(run, b, M1, "en", [], "text", intake())
    assert "Holding words." in text and "Formal words." not in text
    assert "leave formal_statement empty" in b.calls[0]["system"]
    text, _ = plans.plan_c(run, ScriptBackend({("*", "kit"): dict(kit)}), M1, "en", [], "text",
                           intake(characterised=True))
    assert "Formal words." in text
