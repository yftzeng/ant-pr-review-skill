import pytest

from ant_pr_review.catalog import sensitive_dates_near
from ant_pr_review.contextscan import base_context
from ant_pr_review.i18n import T
from ant_pr_review.intake import (CARD_FIELDS, ask_field, build_intake_from_args, card_line,
                                  parse_key_dates)
from ant_pr_review.timeline import build
from ant_pr_review.ui import ScriptedIO

t = T("en")
SPEC = "2026-11-17 Q3 earnings; 2026-11-18 committee hearing"
KEYS = [{"date": "2026-11-17", "label": "Q3 earnings"},
        {"date": "2026-11-18", "label": "committee hearing"}]


# @S-context-card-020
def test_key_dates_parsed_and_on_the_card():
    assert parse_key_dates(SPEC) == KEYS and parse_key_dates("") == []
    with pytest.raises(ValueError):
        parse_key_dates("17/11 earnings")
    card = build_intake_from_args("outbound", ["x"], lang="en", key_dates=SPEC)["card"]
    assert card["key_dates"] == KEYS and "key_dates" in CARD_FIELDS
    assert "2026-11-17 Q3 earnings" in card_line(t, "key_dates", card)
    for lang in ("en", "zh-TW", "zh-CN"):
        for k in ("card.key_dates.label", "card.key_dates"):
            assert T(lang)(k) != k, (lang, k)


# @S-context-card-020
def test_key_dates_are_checked_like_sensitive_dates():
    near = sensitive_dates_near(["tw"], "2026-11-16", own=KEYS)
    assert {"jurisdiction": "org", "date": "2026-11-17", "note": "Q3 earnings"} in near
    assert not [d for d in sensitive_dates_near(["tw"], "2026-10-01", own=KEYS) if d["jurisdiction"] == "org"]
    ctx = base_context({"jurisdictions": ["tw"], "publish_at": "2026-11-16", "key_dates": KEYS})
    assert any(d["note"] == "Q3 earnings" for d in ctx["sensitive_dates"])
    raw = [{"day": 1, "time": "09:00", "action": "Publish the statement", "category": "white",
            "channel": "", "notes": "", "trigger": "", "stop": "", "audience": "public",
            "paid": False, "promotional": False}]
    out = build(raw, {1: {"category": "white", "reason": ""}}, [], {}, ["white"], "2026-11-16",
                ["tw"], "w", t=t, key_dates=KEYS)
    assert any("Q3 earnings" in w for w in out["steps"][0]["warnings"])


# @S-context-card-020
def test_the_plans_phase_passes_the_cards_key_dates():
    from ant_pr_review.plans import _guarded
    from ant_pr_review.timeline import plan_t
    from helpers import M1, M2, ScriptBackend
    intake = build_intake_from_args("outbound", ["x"], lang="en", publish_at="2026-11-16",
                                    key_dates=SPEC)
    step = {"day": 1, "time": "09:00", "action": "Publish the statement", "category": "white",
            "channel": "site", "notes": "", "trigger": "", "stop": "", "audience": "public",
            "paid": False, "promotional": False, "poll": False, "stage": "alarmed",
            "silence": False}
    b = ScriptBackend({("*", "timeline"): {"steps": [step], "excluded": []},
                       ("*", "classify_means"): {"labels": [{"step": 1, "category": "white",
                                                            "reason": "on the record"}],
                                                 "excluded_flags": []}})
    tl, _, _ = plan_t(b, M1, M2, "en", [], "", intake, _guarded)
    assert any("Q3 earnings" in w for w in tl["steps"][0]["warnings"])


# @S-context-card-020
def test_key_dates_edited_from_the_card_menu_and_asked_again_when_bad():
    from ant_pr_review.intake import run_intake_interactive
    from test_context_card import FILL
    io = ScriptedIO(["", "", "", "", "", "", "Some text", "/done"] + FILL[:-3]
                    + ["2026-10-20", "", "2026-10-22"] + [""])
    card = run_intake_interactive(io, t, "en")["card"]
    assert t("card.key_dates") not in io.text and card.get("key_dates", []) == []
    card = {}
    io = ScriptedIO(["17/11 earnings", SPEC])
    ask_field(io, t, "key_dates", card, "outbound")
    assert card["key_dates"] == KEYS and "YYYY-MM-DD" in io.text
