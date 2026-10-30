"""The shared crisis core in audit and drafting (D-0007): the three times of an event and
unknown facts with an owner and a due time."""
from ant_pr_review import prompts
from ant_pr_review.drafting import check_brief
from ant_pr_review.i18n import T
from ant_pr_review.intake import CARD_FIELDS, build_intake_from_args, card_line
from test_drafting import BRIEF

t = T("en")
TIMES = ("occurred_at", "known_at", "exposed_at")


# @S-context-card-019
def test_card_has_the_three_times():
    i = build_intake_from_args("outbound", ["x"], lang="en", occurred_at="2026-10-20 09:00",
                               known_at="2026-10-21", exposed_at="")
    card = i["card"]
    assert card["occurred_at"] == "2026-10-20 09:00" and card["known_at"] == "2026-10-21"
    assert card["exposed_at"] == ""
    assert all(f in CARD_FIELDS for f in TIMES)
    assert card_line(t, "exposed_at", card) == t("intake.skipped")
    block = prompts.card_block(i)
    assert "2026-10-20 09:00" in block and "known_at" in block
    for lang in ("en", "zh-TW", "zh-CN"):
        for f in TIMES:
            assert T(lang)(f"card.{f}.label") != f"card.{f}.label", (lang, f)
            assert T(lang)(f"card.{f}") != f"card.{f}", (lang, f)


# @S-context-card-019 asked on the card, Enter skips
def test_card_asks_the_three_times():
    from ant_pr_review.intake import run_intake_interactive
    from ant_pr_review.ui import ScriptedIO
    from test_context_card import FILL
    io = ScriptedIO(["", "", "", "", "", "", "Some text", "/done"] + FILL[:-3]
                    + ["2026-10-20", "", "2026-10-22"] + [""])
    card = run_intake_interactive(io, t, "en")["card"]
    assert (card["occurred_at"], card["known_at"], card["exposed_at"]) == \
        ("2026-10-20", "", "2026-10-22")
    assert t("card.known_at") in io.text


# @S-drafting-025
def test_brief_owned_unknowns_and_times():
    b = check_brief(dict(BRIEF, unknown=["Units still in use | quality lead | 2026-10-31 18:00",
                                         {"text": "Cause of the seal fault", "owner": "supplier QA"},
                                         "How many complaints"],
                         confirmed=["Sales stopped | all stores"],
                         occurred_at="2026-10-18", known_at="2026-10-20 14:00"))
    u = [f for f in b["facts"] if f["status"] == "unknown"]
    assert [(f["id"], f["text"], f["owner"], f["due"]) for f in u] == [
        ("U1", "Units still in use", "quality lead", "2026-10-31 18:00"),
        ("U2", "Cause of the seal fault", "supplier QA", ""),
        ("U3", "How many complaints", "", "")]
    c1 = next(f for f in b["facts"] if f["id"] == "C1")
    assert c1["text"] == "Sales stopped | all stores" and "owner" not in c1
    assert (b["occurred_at"], b["known_at"], b["exposed_at"]) == ("2026-10-18", "2026-10-20 14:00", "")
    intake = build_intake_from_args("outbound", [], lang="en", purpose="drafting", brief=dict(
        BRIEF, unknown=["Units still in use | quality lead | 2026-10-31"], known_at="2026-10-20"))
    p = prompts.draft_prompt(intake, intake["brief"], "", [], "")
    assert "quality lead" in p and "2026-10-20" in p and "known_at" in p


# @S-drafting-025 the brief asks them interactively
def test_brief_asks_times_and_owned_unknowns():
    from ant_pr_review.intake import ask_brief
    from ant_pr_review.ui import ScriptedIO
    io = ScriptedIO(["",                                   # kind
                     "Sales stopped", "/done", "/done",    # confirmed, alleged
                     "Units in use | QA lead | 18:00", "/done",
                     "2026-10-18", "2026-10-20", "",       # occurred, known, exposed
                     "",                                   # worst case
                     "buyers", "", "fix", "",              # affected, emotion, outcome, decision
                     "/done", "/done", "/done", "/done",   # prior, actions
                     "", "",                               # approvers, characterised
                     "/done", ""])                         # cannot_commit, tier4
    b = ask_brief(io, t)
    u = next(f for f in b["facts"] if f["status"] == "unknown")
    assert (u["text"], u["owner"], u["due"]) == ("Units in use", "QA lead", "18:00")
    assert (b["occurred_at"], b["known_at"]) == ("2026-10-18", "2026-10-20")
    assert t("brief.known_at") in io.text and "|" in t("brief.unknown")
