"""Crisis-core items in the checklist and the worst case in the brief (D-0007)."""
from ant_pr_review import prompts
from ant_pr_review.catalog import item_index, plan_units
from ant_pr_review.drafting import check_brief
from ant_pr_review.intake import build_intake_from_args
from test_drafting import BRIEF


# @S-checklist-022
def test_crisis_core_items():
    idx = item_index()
    expect = {
        "INT-09": ("sign", "first know", "independent test", "records request", "worst case",
                   "evidence could the other side"),
        "REG-07": ("first knew", "deadline", "counsel", "without a record"),
        "STK-08": ("frontline", "read aloud", "match", "refer"),
        "JOU-19": ("press conference", "trained", "rehearsed", "length", "host",
                   "core questions", "recorded", "walk-out", "cut-off"),
    }
    for item, needles in expect.items():
        text = idx[item]["text"]
        for n in needles:
            assert n.lower() in text.lower(), (item, n)
    units = plan_units("outbound", ["internal", "regulator", "stakeholders", "journalist"],
                       ["tw"], "quick", "clarify_apologize", ["responsible:organization"])
    asked = {i for u in units for i in u["items"]}
    assert {"INT-09", "REG-07", "STK-08", "JOU-19"} <= asked


# @S-drafting-026
def test_worst_case_and_proportion_hint():
    b = check_brief(dict(BRIEF, worst_case="  up to 5,000 units of the March batch "))
    assert b["worst_case"] == "up to 5,000 units of the March batch"
    assert check_brief(dict(BRIEF))["worst_case"] == ""
    intake = build_intake_from_args("outbound", [], lang="en", purpose="drafting",
                                    brief=dict(BRIEF, worst_case="up to 5,000 units"))
    p = prompts.draft_prompt(intake, intake["brief"], "", [], "")
    assert "up to 5,000 units" in p
    s = prompts.draft_system("en", intake, tier4=False, holding=False)
    assert "promises nothing beyond the worst case" in s
    assert "two fifths" in s and "guide only" in s
    held = prompts.draft_system("en", intake, tier4=False, holding=True)
    assert "two fifths" not in held and "promises nothing beyond the worst case" in held


# @S-drafting-026 asked after the three times
def test_brief_asks_worst_case():
    from ant_pr_review.i18n import T
    from ant_pr_review.intake import ask_brief
    from ant_pr_review.ui import ScriptedIO
    t = T("en")
    io = ScriptedIO(["", "Sales stopped", "/done", "/done", "/done",
                     "", "", "",                      # the three times
                     "up to 5,000 units",             # worst case
                     "buyers", "", "fix", "", "/done", "/done", "/done", "/done",
                     "", "", "/done", ""])
    b = ask_brief(io, t)
    assert b["worst_case"] == "up to 5,000 units" and t("brief.worst_case") in io.text
