"""Our role (standpoint and identity), the stakeholder map and the borrowed items (D-0003)."""
import re
from pathlib import Path

import pytest

from ant_pr_review import prompts
from ant_pr_review.catalog import (DEFAULT_LENSES, DIRECTIONS, PARTY_GROUPS, PARTY_TYPES,
                                   identity_options, item_index, party_info, party_types_for,
                                   plan_units, validate_items)
from ant_pr_review.consensus import synthesize
from ant_pr_review.i18n import T
from ant_pr_review.intake import (ask_identities, ask_standpoints, build_intake_from_args,
                                  card_stakeholders, roles_of)
from ant_pr_review.jsonio import read_json, write_json
from ant_pr_review.plans import run_plans
from ant_pr_review.report import stakeholder_lines
from ant_pr_review.roster import slug
from ant_pr_review.store import DEFAULT_THRESHOLDS
from ant_pr_review.ui import ScriptedIO
from helpers import M1, M2, ScriptBackend, make_run, ok, recs, review_data

t = T("en")
Q = lambda *_: None
ROOT = Path(__file__).resolve().parents[1]


# ---- intake --------------------------------------------------------------------------

# @S-context-card-014
def test_standpoint_checkbox_and_identities_follow_it():
    assert ask_standpoints(ScriptedIO([""]), t) == ["responsible"]
    io = ScriptedIO([""])
    assert ask_identities(io, t, ["responsible"]) == ["responsible:organization"]
    assert "affected:" not in "".join(identity_options(["responsible"]))
    opts = identity_options(["responsible", "affected"])
    assert "affected:victims" in opts and "responsible:board" in opts
    io = ScriptedIO(["1", "", "2", ""])
    assert ask_standpoints(io, t) == ["affected"] and "Choose at least 1" in io.text


# @S-context-card-015 @N-context-card-001
def test_astroturf_never_our_identity():
    for sp in ("responsible", "affected", "related"):
        assert not any(o.endswith(":astroturf") for o in identity_options([sp]))
    with pytest.raises(ValueError, match="astroturf"):
        build_intake_from_args("outbound", ["x"], lang="en", roles=["related:astroturf"])
    it = build_intake_from_args("outbound", ["x"], lang="en", roles=["related:short_activists"])
    assert roles_of(it)["identities"] == ["related:short_activists"]
    it = build_intake_from_args("outbound", ["x"], lang="en", roles=["responsible:ruling_party"])
    assert roles_of(it)["identities"] == ["responsible:ruling_party"]
    all_opts = identity_options(["responsible", "affected", "related"])
    assert not any(":cn_" in o or ":tw_" in o for o in all_opts)
    assert roles_of({"roles": {"identities": ["related:cn_propaganda"]}})["identities"] == [
        "responsible:organization"]


# @S-context-card-016
def test_roles_from_arguments_and_defaults():
    it = build_intake_from_args("outbound", ["x"], lang="en",
                                roles=["affected:victims", "related:partners"])
    assert roles_of(it) == {"standpoints": ["affected", "related"],
                            "identities": ["affected:victims", "related:partners"]}
    it = build_intake_from_args("outbound", ["x"], lang="en")
    assert roles_of(it) == {"standpoints": ["responsible"],
                            "identities": ["responsible:organization"]}
    assert roles_of({}) == roles_of(it)
    with pytest.raises(ValueError, match="responsible:bystanders"):
        build_intake_from_args("outbound", ["x"], lang="en", roles=["responsible:bystanders"])


# @S-context-card-017
def test_card_stakeholders_use_party_types():
    it = build_intake_from_args("outbound", ["x"], lang="en", stakeholders="board,media")
    assert it["card"]["stakeholders"] == ["board", "media"]
    assert card_stakeholders({"stakeholders": ["consumers", "employees"]}) == [
        "victims", "bystanders", "staff"]
    with pytest.raises(ValueError, match="stakeholder"):
        build_intake_from_args("outbound", ["x"], lang="en", stakeholders="wizards")


# ---- checklist -----------------------------------------------------------------------

def _all(units):
    return {i for u in units for i in u["items"]}


# @S-checklist-011
def test_stakeholders_lens_per_jurisdiction():
    stk = {f"STK-0{n}" for n in range(1, 7)}
    for d in DIRECTIONS:
        for depth in ("quick", "full"):
            units = plan_units(d, DEFAULT_LENSES[d], ["tw", "us"], depth)
            for j in ("tw", "us"):
                assert stk <= _all([u for u in units if u["scope"] == j]), (d, depth, j)
            assert not stk & _all([u for u in units if u["scope"] == "global"])


# @S-checklist-012
def test_role_items_only_for_matching_identity():
    board = _all(plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw"], "quick",
                            identities=["responsible:board"]))
    short = _all(plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw"], "quick",
                            identities=["related:short_activists"]))
    assert "ROL-01" in board and "ROL-04" not in board
    assert "ROL-04" in short and "ROL-01" not in short
    bad = [{"id": "X-01", "lens": "legal", "directions": ["outbound"], "dimension": "legal",
            "roles": ["wizards"], "text": "?"}]
    with pytest.raises(ValueError, match="party type"):
        validate_items(bad)
    unit = plan_units("outbound", ["legal"], ["tw"], "quick", identities=["responsible:board"])[0]
    p = prompts.review_prompt({"direction": "outbound", "card": {},
                               "roles": {"standpoints": ["responsible"],
                                         "identities": ["responsible:board"]}}, unit, "x")
    assert "Our role: responsible:board" in p


# @S-checklist-013
def test_borrowed_items_exist_and_are_credited():
    idx = item_index()
    borrowed = ["JOU-06", "JOU-07", "JOU-08", "JOU-09", "SOC-07", "SOC-08", "INT-04", "RSP-04",
                "APO-03", "EXP-04"]
    assert set(borrowed) <= set(idx)
    refs = (ROOT / "docs" / "REFERENCES.md").read_text()
    for i in borrowed:
        assert i in refs, i
    assert "e85f3cbc2e4a79bf33b2a12e9bdd9087d414735b" in refs
    assert "4e7f4f8e389847757a5a4236c2f1ed9813359179" in refs


# ---- stakeholder matrix --------------------------------------------------------------

def _stk(skip=(), relevance="high", L=2, I=3, scope="tw"):
    return [{"type": p, "relevance": relevance, "reaction": f"r-{p}", "needs": "n",
             "handling": "h", "likelihood": L, "impact": I} for p in party_types_for(scope)
            if p not in skip]


# @S-review-matrix-027
def test_every_party_type_answered_and_gaps_listed():
    units = plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw"], "quick")
    tw = next(u for u in units if u["scope"] == "tw")
    gl = next(u for u in units if u["scope"] == "global")
    d1 = dict(review_data(items=tw["items"]), stakeholders=_stk(L=4))
    d2 = dict(review_data(items=tw["items"]), stakeholders=_stk(skip=["board"], relevance="low"))
    matrix = {"direction": "outbound", "jurisdictions": ["tw"], "units": units}
    reviews = recs((tw["id"], M1, d1), (tw["id"], M2, d2),
                   (gl["id"], M1, review_data(items=gl["items"])),
                   (gl["id"], M2, review_data(items=gl["items"])))
    syn = synthesize(matrix=matrix, reviews=reviews, debates={}, ledger=[], models=[M1, M2],
                     thresholds=DEFAULT_THRESHOLDS)
    rows = syn["jurisdictions"]["tw"]["stakeholders"]
    assert [r["type"] for r in rows] == party_types_for("tw")
    assert {"tw_dpp", "tw_kmt", "tw_tpp"} <= {r["type"] for r in rows}
    assert "ruling_party" not in {r["type"] for r in rows}
    board = next(r for r in rows if r["type"] == "board")
    assert board["unanswered"] == [M2] and set(board["by_model"]) == {M1}
    media = next(r for r in rows if r["type"] == "media")
    assert media["relevance"] == "high" and media["score"] == 12
    assert set(media["by_model"]) == {M1, M2}


# @S-review-matrix-028
def test_report_stakeholder_section_grouped():
    rows = [{"type": p, "group": party_info(p)["group"], "relevance": "high", "score": 6,
             "unanswered": [],
             "by_model": {M1: {"relevance": "high", "reaction": f"react-{p}", "needs": "need",
                               "handling": "handle", "likelihood": 2, "impact": 3}}}
            for p in party_types_for("tw")]
    text = "\n".join(stakeholder_lines(t, rows, [M1, M2]))
    for g in PARTY_GROUPS:
        assert t(f"group.{g}") in text
    assert "react-board" in text and "need" in text and "handle" in text
    assert f"{M2} ∅" in text and "Kuomintang" in text


# @S-review-matrix-028
def test_report_header_names_our_role(tmp_path, monkeypatch):
    import ant_pr_review.cli as cli
    from ant_pr_review.backends.fake import FakeBackend
    from ant_pr_review.store import Store
    from ant_pr_review.workspace import list_runs
    monkeypatch.setattr(cli, "get_backend", lambda name: FakeBackend())
    store = Store(tmp_path / "home")
    cli.main(["new", "--yes", "--backend", "fake", "--role", "responsible:board", "--target",
              "# P\n\nText."], io=ScriptedIO(), store=store)
    md = list_runs(store.runs_dir)[-1].path("08-report.v1.md").read_text()
    assert "Our role: Responsible - Board and controlling shareholders" in md
    assert "## Stakeholder map" in md and "ROL-01" in md


# ---- plans ---------------------------------------------------------------------------

RISK = {"id": "R01", "anchor": "D1.P02.S1", "dimension": "backlash", "scope": "tw",
        "scenario": "s", "standard": "std", "mitigation": "m", "score": 6}
KIT = {"holding_statement": "We are looking into it.", "qa": [],
       "monitoring_keywords": [{"term": "Acme recall", "kind": "issue", "platforms": ["PTT"]},
                               {"term": "@someone", "kind": "brand", "platforms": []},
                               {"term": "艾克米", "kind": "variant", "platforms": ["Dcard"]}],
       "escalation": [], "do_not_say": []}


def _setup(tmp_path):
    run = make_run(tmp_path, text="# T\n\nOur statement.")
    for m in (M1, M2):
        write_json(run.path(f"04-reviews/tw.all/{slug(m)}.json"), ok(m, "tw.all", review_data()))
    write_json(run.path("06-synthesis.json"), {"risks": [RISK], "unverified": [],
                                               "jurisdictions": {}})
    return run


def _step(day, time, action, audience, paid=False, stop=""):
    return {"day": day, "time": time, "action": action, "category": "white", "channel": "web",
            "notes": "n", "trigger": "", "stop": stop, "audience": audience, "paid": paid}


# @S-plans-029
def test_press_before_affected_and_paid_without_stop_are_warned(tmp_path):
    run = _setup(tmp_path)
    steps = [_step(0, "10:00", "Tell affected customers", "affected"),
             _step(0, "09:00", "Press release", "press"),
             _step(1, "09:00", "Paid boost", "public", paid=True)]
    b = ScriptBackend({(M1, "timeline"): {"steps": steps, "excluded": []},
                       (M2, "classify_means"): {"labels": [
                           {"step": n, "category": "white", "reason": ""} for n in (1, 2, 3)],
                           "excluded_flags": []},
                       (M1, "plan_a"): {"paragraphs": [], "corrections": []},
                       (M1, "plan_b"): {"recommendation": "publish_revised", "paragraphs": [],
                                        "headline_options": [], "alternative": "", "notes": ""},
                       (M1, "kit"): KIT, ("*", "rereview"): {"verdicts": []}})
    run_plans(run, b, [M1, M2], "en", say=Q)
    steps = {s["action"]: s for s in read_json(run.path("09-plans/T.json"))["steps"]}
    assert any("affected" in w for w in steps["Press release"]["warnings"])
    assert not steps["Tell affected customers"]["warnings"]
    assert any("no stop condition" in w for w in steps["Paid boost"]["warnings"])


# @S-plans-030
def test_monitoring_keywords_are_typed_and_handles_dropped(tmp_path):
    run = _setup(tmp_path)
    b = ScriptBackend({(M1, "kit"): KIT, (M1, "plan_a"): {"paragraphs": [], "corrections": []},
                       (M1, "plan_b"): {"recommendation": "publish_revised", "paragraphs": [],
                                        "headline_options": [], "alternative": "", "notes": ""},
                       ("*", "rereview"): {"verdicts": []}})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    kit = run.path("09-plans/C-kit.md").read_text()
    assert "Acme recall" in kit and "艾克米" in kit and "@someone" not in kit
    assert re.search(r"issue.*Acme recall", kit, re.I)
    assert any("dropped" in w for w in out["warnings"])
    assert not any("@someone" in w for w in out["warnings"])


# @S-review-matrix-027
def test_stakeholder_answers_cleaned_per_unit():
    from ant_pr_review.review import clean_review
    units = plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw"], "quick")
    tw = next(u for u in units if u["scope"] == "tw")
    gl = next(u for u in units if u["scope"] == "global")
    rows = _stk(L=9) + [{"type": "wizards", "relevance": "high", "reaction": "", "needs": "",
                         "handling": "", "likelihood": 1, "impact": 1}] + _stk()[:1]
    got = clean_review(dict(review_data(items=tw["items"]), stakeholders=rows), tw)["stakeholders"]
    assert [r["type"] for r in got] == party_types_for("tw") and got[0]["likelihood"] == 5
    assert clean_review(dict(review_data(items=gl["items"]), stakeholders=rows),
                        gl)["stakeholders"] == []


# ---- tier-3 review findings --------------------------------------------------------------

# @S-context-card-015 @N-context-card-001
@pytest.mark.parametrize("ids", [["related:astroturf"], ["responsible:bystanders"], ["astroturf"],
                                 "responsible:board", [3, None], [], {"a": 1}, ["x:"]])
def test_a_stored_intake_never_carries_an_unreasonable_identity(ids):
    roles = roles_of({"roles": {"identities": ids}})
    assert not any(i.endswith(":astroturf") for i in roles["identities"])
    assert all(i in identity_options(["responsible", "affected", "related"])
               for i in roles["identities"])
    assert roles["identities"]  # falls back to the default rather than nothing
    if ids == "responsible:board":
        assert roles["identities"] == ["responsible:board"]
    p = prompts.role_block({"roles": {"identities": ids}})
    assert "astroturf" not in p and "bystanders" not in p


# @S-context-card-017
def test_legacy_stakeholders_survive_an_edit_and_reach_the_prompt():
    from ant_pr_review.intake import ask_field
    card = {"stakeholders": ["consumers", "custom:foo"]}
    ask_field(ScriptedIO([""]), t, "stakeholders", card, "outbound")
    assert card["stakeholders"] == ["victims", "bystanders", "custom:foo"]
    assert "consumers" not in prompts.card_block({"card": {"stakeholders": ["consumers"]}})
    it = build_intake_from_args("outbound", ["x"], lang="en", stakeholders="consumers,board")
    assert it["card"]["stakeholders"] == ["victims", "bystanders", "board"]


# @S-plans-029
@pytest.mark.parametrize("steps,posture,warned", [
    # no affected step at all in a crisis posture: the first press step warns
    ([("Press release", "press", 0, "09:00")], "clarify_apologize", ["Press release"]),
    # promotion has no affected parties to tell first
    ([("Press release", "press", 0, "09:00")], "promote", []),
    # a tie is not "after"
    ([("Press release", "press", 0, "09:00"), ("Tell customers", "affected", 0, "09:00")],
     "clarify_apologize", ["Press release"]),
    # a press step without a readable time on the affected day counts as early
    ([("Tell customers", "affected", 0, "10:00"), ("Press release", "press", 0, "")],
     "clarify_apologize", ["Press release"]),
    # staff after the public
    ([("Tell customers", "affected", 0, "08:00"), ("Post", "public", 0, "09:00"),
      ("Staff memo", "staff", 0, "12:00")], "clarify_apologize", ["Staff memo"]),
    ([("Tell customers", "affected", 0, "08:00"), ("Staff memo", "staff", 0, "08:30"),
      ("Press release", "press", 0, "09:00")], "clarify_apologize", []),
])
def test_audience_order_rules(steps, posture, warned):
    from ant_pr_review.timeline import build
    raw = [{"day": d, "time": tm, "action": a, "category": "white", "channel": "", "notes": "",
            "trigger": "", "stop": "", "audience": aud, "paid": False} for a, aud, d, tm in steps]
    labels = {n: {"category": "white", "reason": ""} for n in range(1, len(raw) + 1)}
    out = build(raw, labels, [], {}, ["white", "gray"], "", ["tw"], "w", t=t, posture=posture)
    got = [s["action"] for s in out["steps"] if any(
        "affected" in w or "staff" in w for w in s["warnings"])]
    assert got == warned


# @S-plans-030
@pytest.mark.parametrize("bad", ["＠bob", "u/bob_real", "t.me/x", "Acme @bob",
                                 "https://ptt.cc/user/x", "www.example.com/bob"])
def test_handles_and_links_are_never_monitoring_keywords(bad):
    from ant_pr_review.plans import kit_keywords
    kept, warn = kit_keywords({"monitoring_keywords": [
        {"term": bad, "kind": "officer", "platforms": []},
        None, 123, {"term": "Acme", "kind": "weird", "platforms": "PTT"}]})
    assert [k["term"] for k in kept] == ["Acme"]
    assert kept[0]["kind"] == "brand" and kept[0]["platforms"] == ["PTT"]
    assert warn and not any(bad in w for w in warn)
    assert kit_keywords({"monitoring_keywords": None}) == ([], [])


# @S-review-matrix-027
def test_relevance_is_normalised_and_missing_types_are_retried_and_reported(tmp_path):
    from ant_pr_review.review import clean_review, run_round1
    units = plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw"], "quick")
    tw = next(u for u in units if u["scope"] == "tw")
    rows = _stk()
    rows[0] = dict(rows[0], relevance="high | <script>x</script>")
    rows[1] = {k: v for k, v in rows[1].items() if k != "relevance"}
    got = clean_review(dict(review_data(items=tw["items"]), stakeholders=rows), tw)["stakeholders"]
    assert got[0]["relevance"] == "none" and got[1]["relevance"] == "none"
    run = make_run(tmp_path, models=(M1,))
    calls = []

    def h(prompt):
        calls.append(prompt)
        items = re.findall(r"^- ([A-Z]{3}-\d{2}) \[", prompt, re.M)
        scope = "tw" if "Jurisdiction: Taiwan" in prompt else "global"
        first_tw = scope == "tw" and sum("Jurisdiction: Taiwan" in c for c in calls) == 1
        skip = ["board"] if first_tw else []
        return dict(review_data(items=items), stakeholders=_stk(skip=skip, scope=scope)
                    if "stakeholders:" in prompt and "EVERY party" in prompt else [])
    run_round1(run, ScriptBackend({("*", "review"): h}), [M1], "en", say=Q)
    rec = read_json(run.path(f"04-reviews/tw.all/{slug(M1)}.json"))
    assert any("omitted these stakeholder party types: board" in c for c in calls)
    assert rec["unanswered_types"] == []
    assert len(rec["data"]["stakeholders"]) == len(party_types_for("tw"))


# @S-review-matrix-028
def test_stakeholder_section_is_compact_and_gaps_are_not_none():
    rows = [{"type": p, "group": party_info(p)["group"], "relevance": "none", "score": 0,
             "unanswered": [],
             "by_model": {m: {"relevance": "none", "reaction": "", "needs": "", "handling": "",
                              "likelihood": 0, "impact": 0} for m in (M1, M2)}}
            for p in party_types_for("tw")]
    rows[1] = dict(rows[1], relevance="high", score=12,
                   by_model={M1: {"relevance": "high", "reaction": "sue", "needs": "n",
                                  "handling": "h", "likelihood": 3, "impact": 4}},
                   unanswered=[M2])
    rows[2] = dict(rows[2], by_model={}, unanswered=[M1, M2])
    lines = stakeholder_lines(t, rows, [M1, M2])
    text = "\n".join(lines)
    gov = text.split("**")[2]
    assert gov.index(t("party.board")) < gov.index(t("party.executives"))
    fans = next(ln for ln in lines if t("party.fans") in ln)
    assert M1 in fans and M2 in fans  # one line for both models
    i = lines.index(fans)
    assert not lines[i + 1].startswith("| | | |")
    staff = next(ln for ln in lines if t("party.staff") in ln)
    assert "∅" in staff and t("relevance.none") not in staff


# @S-checklist-014
def test_stress_tests_per_jurisdiction():
    stress = {f"RTM-0{n}" for n in range(1, 6)} | {"POL-01", "POL-02", "POL-03"}
    for d in ("outbound", "inbound"):
        units = plan_units(d, DEFAULT_LENSES[d], ["tw", "cn"], "quick")
        for j in ("tw", "cn"):
            assert stress <= _all([u for u in units if u["scope"] == j])
        assert not stress & _all([u for u in units if u["scope"] == "global"])
    assert not stress & _all(plan_units("operation", DEFAULT_LENSES["operation"], ["tw"],
                                        "quick"))
    assert "STK-07" in _all(plan_units("operation", DEFAULT_LENSES["operation"], ["tw"], "quick"))
    assert {"cn_propaganda", "cn_tao", "cn_arats"} <= set(party_types_for("cn"))
    assert "eu_governments" in party_types_for("eu") and "us_gop" in party_types_for("us")
    assert "ruling_party" not in party_types_for("eu")


# @S-review-matrix-029
def test_report_stress_section():
    from ant_pr_review.report import stress_lines
    items = [{"item": "RTM-01", "unit": "tw.all", "verdict": "fail", "label": "",
              "by_model": {M1: "fail"}, "unanswered": [M2], "score": 12,
              "evidence": {M1: "「我們願意負起全部賠償責任」 admits liability"}},
             {"item": "POL-03", "unit": "tw.all", "verdict": "pass", "label": "",
              "by_model": {M1: "pass", M2: "pass"}, "unanswered": [], "score": 0,
              "evidence": {M1: "same terms", M2: "same"}}]
    text = "\n".join(stress_lines(T("zh-TW"), items, [M1, M2]))
    assert "法律底線" in text and "主權與合規紅線測試" in text
    assert "對造律師" in text and "負起全部賠償責任" in text and f"{M2} ∅" in text
    assert "░░░░░░░░░░   0%  0/1" in text


# ---- second review round ---------------------------------------------------------------

# @S-context-card-015 @N-context-card-001
def test_a_political_identity_is_refused_where_the_ruling_party_is_a_state_organ():
    with pytest.raises(ValueError, match="cn"):
        build_intake_from_args("outbound", ["x"], lang="en", jurisdictions="tw,cn",
                               roles=["responsible:ruling_party"])
    stored = {"card": {"jurisdictions": ["cn"]},
              "roles": {"identities": ["responsible:ruling_party", "related:board"]}}
    roles = roles_of(stored)
    assert roles["identities"] == ["related:board"] and roles["dropped"]
    it = build_intake_from_args("outbound", ["x"], lang="en", jurisdictions="tw",
                                roles=["responsible:ruling_party"])
    assert "Democratic Progressive Party" in prompts.role_block(it)


# @S-checklist-011
def test_prompts_forbid_state_influence_work_and_profiling_of_individuals():
    assert "influence operation" in prompts.ETHICS_RULES
    unit = next(u for u in plan_units("outbound", DEFAULT_LENSES["outbound"], ["cn"], "quick")
                if u["scope"] == "cn")
    task = prompts.stakeholder_task(unit)
    assert "never how to influence" in task and "a role, not a person" in task


# @S-review-matrix-029
def test_stress_lines_name_the_unit_parties_once_per_item():
    from ant_pr_review.report import stress_lines
    mk = lambda unit: {"item": "POL-01", "unit": unit, "verdict": "pass", "label": "",
                       "by_model": {M1: "pass"}, "unanswered": [], "score": 0,
                       "evidence": {M1: "ok"}}
    text = "\n".join(stress_lines(t, [mk("tw.all"), mk("cn.all"), mk("us.all")], [M1]))
    assert text.count("> ") == 1
    assert "Kuomintang" in text and "Democratic Party" in text
    tw_line = next(ln for ln in text.splitlines() if "`tw.all`" in ln)
    assert "Opposition party" not in tw_line and "Republican" not in tw_line


# @S-review-matrix-029
def test_merger_sees_cross_region_evidence_only_from_the_panels():
    from ant_pr_review.jmerge import summary_for
    o = {"verdict": "go", "provisional": False, "red_lines": {}, "risks": [],
         "items": [{"item": "POL-03", "unit": "tw.all", "verdict": "pass", "label": "",
                    "evidence": {M1: "uses 'Taiwan (ROC)'"}, "by_model": {M1: "pass"}}]}
    s = summary_for({"jurisdictions": {"tw": o}}, "tw")
    assert s["cross_region"] == [{"item": "POL-03", "evidence": ["uses 'Taiwan (ROC)'"]}]
    assert "only when" in prompts.compare_prompt({"tw": s})


# @S-review-matrix-027
def test_eu_politics_rows_and_partial_stakeholder_records():
    assert {"eu_governments", "eu_parliament_groups"} <= set(party_types_for("eu"))
    from ant_pr_review.consensus import tally_stakeholders
    unit = {"id": "tw.all", "scope": "tw", "lenses": ["stakeholders"], "items": []}
    recs_ = {M1: {"status": "ok", "data": {"stakeholders": [{"type": "board"}]}}}
    rows = tally_stakeholders(unit, recs_, [M1])
    assert next(r for r in rows if r["type"] == "board")["score"] == 0


# @S-checklist-007
def test_a_dated_sensitive_date_only_warns_in_its_year():
    from ant_pr_review.catalog import sensitive_dates_near
    assert any("local elections" in d["note"] for d in sensitive_dates_near(["tw"], "2026-11-27"))
    assert not any("local elections" in d["note"]
                   for d in sensitive_dates_near(["tw"], "2027-11-27"))
    assert any("midterm" in d["note"] for d in sensitive_dates_near(["us"], "2026-11-02"))


# @S-review-matrix-027
def test_review_schema_accepts_a_pack_party_answer():
    from ant_pr_review.schemas import review_schema, validate
    data = dict(review_data(items=[]), stakeholders=[
        {"type": "tw_dpp", "relevance": "high", "reaction": "r", "needs": "n", "handling": "h",
         "likelihood": 2, "impact": 3}])
    assert validate(data, review_schema()) == []
    bad = dict(data, stakeholders=[dict(data["stakeholders"][0], type="martians")])
    assert validate(bad, review_schema())


# @S-checklist-012
def test_party_and_individual_role_items_and_stk07():
    pol = _all(plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw"], "quick",
                          identities=["responsible:ruling_party"]))
    ind = _all(plan_units("inbound", DEFAULT_LENSES["inbound"], ["tw"], "quick",
                          identities=["responsible:implicated_individual"]))
    assert "ROL-12" in pol and "ROL-13" not in pol and "ROL-13" in ind
    for d in ("outbound", "inbound"):
        assert "STK-07" in _all(plan_units(d, DEFAULT_LENSES[d], ["tw"], "quick"))


# @S-review-matrix-028
def test_no_stakeholder_section_for_reviews_that_predate_it_and_names_follow_the_language():
    from ant_pr_review.report import party_label
    assert party_label(T("zh-CN"), "cn_cac").startswith("网信办")
    assert party_label(T("zh-TW"), "cn_cac").startswith("網信辦")
    assert party_label(T("en"), "cn_cac").startswith("Cyberspace Administration")


# @S-review-matrix-028
def test_reviews_without_stakeholder_answers_render_no_map(tmp_path, monkeypatch):
    import ant_pr_review.cli as cli
    from ant_pr_review.backends.fake import FakeBackend
    from ant_pr_review.report import render
    from ant_pr_review.store import Store
    from ant_pr_review.workspace import list_runs
    monkeypatch.setattr(cli, "get_backend", lambda name: FakeBackend())
    store = Store(tmp_path / "home")
    cli.main(["new", "--yes", "--backend", "fake", "--target", "# P\n\nText."], io=ScriptedIO(),
             store=store)
    run = list_runs(store.runs_dir)[-1]
    syn = read_json(run.path("06-synthesis.json"))
    assert "## Stakeholder map" in render(run, syn, lang="en", version=9, changelog=[])
    for o in syn["jurisdictions"].values():
        o["stakeholders"] = [dict(r, by_model={}, unanswered=[]) for r in o["stakeholders"]]
    assert "## Stakeholder map" not in render(run, syn, lang="en", version=9, changelog=[])
