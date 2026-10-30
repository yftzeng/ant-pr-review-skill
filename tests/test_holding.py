"""The six-part holding statement, its channel versions, a frontline Q&A and the order of
audiences in the timeline (D-0007)."""
import pytest

from ant_pr_review import plans, prompts
from ant_pr_review.i18n import T
from ant_pr_review.jsonio import write_json
from ant_pr_review.schemas import HOLDING_FIELDS, KIT, CHANNEL_FIELDS, validate
from ant_pr_review.timeline import build
from helpers import M1
from test_plans import backend, setup, Q

t = T("en")
BLANK = "〔　　〕"
HOLD = {"acknowledge": "We know that some units of the March batch overheated.",
        "confirmed": "Three customers reported it on 28 October.",
        "doing": "We stopped sales of the batch and are testing returned units.",
        "affected_action": "Stop using the unit and call the service line.",
        "contact": "Service line 0800-000-000",
        "next_update": "We will update by 18:00 on 30 October."}
CHANNELS = {"web": "Web text.", "social": "Short post.", "phone": "What to say on a press call.",
            "frontline": "What the service desk says.", "direct": "SMS to affected buyers."}
KIT_NEW = {"holding": HOLD, "channels": CHANNELS, "formal_statement": "",
           "qa": [], "frontline_qa": [{"question": "Is my unit safe?",
                                       "answer": "Stop using it and call us; we replace it."}],
           "monitoring_keywords": [], "escalation": [], "do_not_say": []}


# @S-plans-043
def test_holding_statement_in_six_parts():
    assert HOLDING_FIELDS == ("acknowledge", "confirmed", "doing", "affected_action", "contact",
                              "next_update")
    assert not validate(KIT_NEW, KIT)
    d, warn = plans.holding_shape(dict(KIT_NEW))
    assert warn == []
    md = plans.render_kit(t, d)
    for part in HOLD.values():
        assert part in md
    for k in CHANNEL_FIELDS:
        assert f"### {t('plans.channel.' + k)}" in md and CHANNELS[k] in md
    for lang in ("zh-TW", "zh-CN"):
        assert T(lang)("plans.channel.frontline") != t("plans.channel.frontline")


# @S-plans-043 an empty part or a vague next update becomes a blank with a warning
@pytest.mark.parametrize("field,value", [("contact", ""), ("doing", "  "),
                                         ("next_update", "We will update as soon as possible."),
                                         ("next_update", "我們將盡快說明。"),
                                         ("next_update", "Later today.")])
def test_holding_gaps_are_blanks(field, value):
    d, warn = plans.holding_shape(dict(KIT_NEW, holding=dict(HOLD, **{field: value})))
    assert d["holding"][field] == BLANK
    assert len(warn) == 1 and field in warn[0]
    assert BLANK in plans.render_kit(t, d)


# @S-plans-043 the earlier single text renders as before
def test_old_kit_renders_as_before():
    old = {"holding_statement": "We are looking into it.", "qa": [], "monitoring_keywords": [],
           "escalation": [], "do_not_say": []}
    d, warn = plans.holding_shape(dict(old))
    assert warn == [] and "We are looking into it." in plans.render_kit(t, d)


# @S-plans-043 @S-plans-044 in the run's kit file and prompt
def test_kit_prompt_and_file(tmp_path):
    s = prompts.kit_system("en")
    for needle in ("acknowledge", "affected_action", "next_update", "a clock time",
                   "frontline_qa", "read aloud", "never beyond"):
        assert needle in s, needle
    run = setup(tmp_path)
    b = backend({(M1, "kit"): dict(KIT_NEW, holding=dict(HOLD, contact=""))})
    out = plans.run_plans(run, b, [M1], "en", say=Q)
    md = run.path("09-plans/C-kit.md").read_text(encoding="utf-8")
    assert f"## {t('plans.frontline_qa')}" in md and "Is my unit safe?" in md
    assert BLANK in md and any("contact" in w for w in out["warnings"])


def steps(*rows):
    raw = [{"day": d, "time": tm, "action": a, "category": "white", "channel": "", "notes": "",
            "trigger": "", "stop": "", "audience": aud, "paid": False} for a, aud, d, tm in rows]
    return raw, {n: {"category": "white", "reason": ""} for n in range(1, len(raw) + 1)}


# @S-plans-045
@pytest.mark.parametrize("rows,warned", [
    ([("Tell customers", "affected", 0, "08:00"), ("Brief the regulator", "regulators", 0, "10:00"),
      ("Press release", "press", 0, "09:00")], ["Press release"]),
    ([("Tell customers", "affected", 0, "08:00"), ("Call partners", "partners", 0, "09:00"),
      ("Post", "public", 0, "09:00")], ["Post"]),
    ([("Tell customers", "affected", 0, "08:00"), ("Brief the regulator", "regulators", 0, "08:30"),
      ("Press release", "press", 0, "09:00")], []),
    ([("Tell customers", "affected", 0, "08:00"), ("Press release", "press", 0, "09:00")], []),
])
def test_regulators_and_partners_before_the_press(rows, warned):
    raw, labels = steps(*rows)
    out = build(raw, labels, [], {}, ["white"], "", ["tw"], "w", t=t)
    w = t("plans.t.warn_before_regulators")
    assert [s["action"] for s in out["steps"] if w in s["warnings"]] == warned


# @S-plans-046
@pytest.mark.parametrize("grade,paused", [("I", True), ("II", True), ("III", True),
                                          ("IV", False), (None, False)])
def test_pause_promotions_at_grade_three_or_higher(grade, paused):
    raw, labels = steps(("Tell customers", "affected", -1, "08:00"),
                        ("Press release", "press", 0, "09:00"))
    out = build(raw, labels, [], {}, ["white"], "", ["tw"], "w", t=t, grade=grade)
    first = out["steps"][0]
    if paused:
        assert first["fixed"] and first["action"] == t("plans.t.pause_promo")
        assert first["category"] == "white" and first["audience"] == "staff"
        assert first["day"] == -1 and first["n"] == 1 and len(out["steps"]) == 3
        assert first["warnings"] == []
    else:
        assert not any(s.get("fixed") for s in out["steps"]) and len(out["steps"]) == 2


# @S-plans-046 run_plans passes the run's grade
def test_run_plans_pauses_promotions_on_a_graded_run(tmp_path):
    from ant_pr_review.jsonio import read_json
    run = setup(tmp_path)
    intake = read_json(run.path("00-intake.json"))
    intake["card"]["signals"] = ["social_spread"]          # grade III
    write_json(run.path("00-intake.json"), intake)
    tl = {"steps": [{"day": 0, "time": "09:00", "action": "Press release", "category": "white",
                     "channel": "", "notes": "", "trigger": "", "stop": "", "audience": "press",
                     "paid": False}], "excluded": []}
    b = backend({(M1, "timeline"): tl, ("*", "classify_means"): {
        "labels": [{"step": 1, "category": "white", "reason": ""}], "excluded_flags": []}})
    plans.run_plans(run, b, [M1], "en", say=Q)
    md = run.path("09-plans/T.md").read_text(encoding="utf-8")
    assert t("plans.t.pause_promo") in md, md
    first = read_json(run.path("09-plans/T.json"))["steps"][0]
    assert first["fixed"] and first["warnings"] == []  # never "staff hear this late"
