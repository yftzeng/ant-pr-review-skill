"""Crisis mode: the event alone, no questions, a printable sheet (D-0007)."""
import sys

import pytest

from ant_pr_review import cli, crisis, prompts
from ant_pr_review.i18n import T
from ant_pr_review.intake import PURPOSES, build_intake_from_args, run_intake_interactive
from ant_pr_review.jsonio import read_json, write_json
from ant_pr_review.store import Store
from ant_pr_review.ui import ScriptedIO
from ant_pr_review.workspace import PHASES, list_runs
from helpers import M1, M2

t = T("en")
EVENT = "Three customers say the March batch of the heater overheated on 28 October."


def crisis_run(store, lang="en", target=EVENT, extra=()):
    rc = cli.main(["new", "--yes", "--backend", "fake", "--models", f"{M1},{M2}", "--lang", lang,
                   "--purpose", "crisis", "--target", target, *extra], io=ScriptedIO(), store=store)
    return rc, list_runs(store.runs_dir)[-1]


# @S-crisis-001 @N-crisis-001
def test_crisis_first_and_nothing_asked_after_the_event():
    assert PURPOSES[0] == "crisis"
    io = ScriptedIO(["1", EVENT, "/done"])     # EOFError on any further question
    it = run_intake_interactive(io, t, "en")
    assert it["purpose"] == "crisis" and it["means"] == ["white", "gray", "black"]
    assert it["posture"] == "clarify_apologize" and it["card"]["characterised"] is False
    assert it["card"]["embargo"] is True and it["card"]["jurisdictions"] == ["tw"]
    assert it["targets"][0]["value"] == EVENT and io.answers == []
    assert t("intake.posture") not in io.text and t("card.org") not in io.text
    it = run_intake_interactive(ScriptedIO(["", "", "", "", "", "", "Some text", "/done"]
                                           + __import__("test_context_card").FILL + [""]),
                                t, "en")
    assert it["purpose"] == "audit"
    for lang in ("en", "zh-TW", "zh-CN"):
        assert T(lang)("intake.purpose.crisis") != "intake.purpose.crisis"


# @S-crisis-002
def test_crisis_from_the_command_line(tmp_path):
    it = build_intake_from_args("outbound", [EVENT], lang="en", purpose="crisis")
    assert it["purpose"] == "crisis" and it["means"] == ["white", "gray", "black"]
    assert it["card"]["embargo"] is True and it["card"]["characterised"] is False
    with pytest.raises(ValueError, match="at least one --target"):
        build_intake_from_args("outbound", [], lang="en", purpose="crisis")
    with pytest.raises(ValueError, match="brief"):
        build_intake_from_args("outbound", [EVENT], lang="en", purpose="crisis", brief={})
    store = Store(tmp_path / "home")
    rc, run = crisis_run(store)
    assert rc == 0 and "three-customers" in run.id


# @S-crisis-003 @S-crisis-004
def test_crisis_run_writes_the_sheet(tmp_path):
    pytest.importorskip("fpdf")
    store = Store(tmp_path / "home")
    rc, run = crisis_run(store, lang="zh-TW")
    assert rc == 0 and run.is_finished()
    st = read_json(run.path("state.json"))["phases"]
    for ph in PHASES:
        if ph not in ("intake", "sources", "crisis"):
            assert st[ph].get("skipped") is True, ph
    md = run.path("crisis.md").read_text(encoding="utf-8")
    tw = T("zh-TW")
    heads = [tw(f"crisis.h.{k}") for k in crisis.SECTIONS]
    at = [md.find(f"## {h}") for h in heads]
    assert -1 not in at and at == sorted(at), list(zip(crisis.SECTIONS, at))
    assert tw("plans.t.pause_promo") in md and tw("crisis.first30.gag") in md
    assert tw("crisis.grade_unconfirmed") in md and tw("crisis.counsel") in md
    for k in ("acknowledge", "next_update"):
        assert tw(f"crisis.holding.{k}") in md
    assert tw("plans.channel.frontline") in md
    assert run.path("crisis.pdf").exists() and run.path("crisis.docx").exists()
    from test_export import pdf_text, flat
    _, ptext = pdf_text(run.path("crisis.pdf"))
    for h in heads:
        assert flat(h) in ptext, h


# @S-crisis-003 the calls, and no prompt even when a source fails
def test_crisis_calls_and_no_prompt_on_a_failed_source(tmp_path, monkeypatch):
    from ant_pr_review.backends.fake import FakeBackend
    calls = []
    real = FakeBackend.run

    def spy(self, model, **kw):
        calls.append(kw["task"])
        return real(self, model, **kw)
    monkeypatch.setattr(FakeBackend, "run", spy)
    store = Store(tmp_path / "home")
    io = ScriptedIO(["1", "http://127.0.0.1:9/x", EVENT, "/done"])  # no DNS lookup
    monkeypatch.setattr(cli, "load_cfg", lambda args, io, store: _cfg(store))
    rc = cli.main(["new", "--backend", "fake", "--models", f"{M1},{M2}", "--no-render"], io=io,
                  store=store)
    run = list_runs(store.runs_dir)[-1]
    assert rc == 0 and run.path("crisis.md").exists() and io.answers == []
    assert sorted(set(calls)) == ["classify_means", "crisis_facts", "kit", "opponent",
                                  "threats", "timeline"]


def _cfg(store):
    cfg = store.load_config()
    cfg.lang = "en"
    return cfg


# @S-crisis-003 an audit marks the crisis phase not applicable
def test_audit_skips_the_crisis_phase(tmp_path):
    store = Store(tmp_path / "home")
    cli.main(["new", "--yes", "--backend", "fake", "--models", f"{M1},{M2}", "--target", EVENT],
             io=ScriptedIO(), store=store)
    run = list_runs(store.runs_dir)[-1]
    assert read_json(run.path("state.json"))["phases"]["crisis"].get("skipped") is True
    assert not run.path("crisis.md").exists()


FACTS = {"summary": "Heaters from the March batch overheated.", "objective": "Keep buyers safe.",
         "suggested_signals": ["social_spread", "complaints_surge", "made_up"],
         "w5h1": {"who": "buyers", "what": "overheating", "when": "28 October", "where": "TW",
                  "why": "", "how": ""},
         "times": {"occurred_at": "2026-10-28", "known_at": "", "exposed_at": ""},
         "verified": [{"fact": "Three reports", "evidence": "service log"}],
         "pending": [{"question": "How many units", "owner_role": "", "due": ""}],
         "rumours": [{"claim": "A fire at a home", "verdict": "false", "counter_evidence": ""},
                     {"claim": "All batches affected", "verdict": "false",
                      "counter_evidence": "the batch log shows one batch"}],
         "impact": {"people": "three reports, no injury", "money": "", "batch_risk": "",
                    "operations": ""},
         "minors": True,
         "stakeholders": [{"group": "press", "need": "facts", "channel": "statement"},
                          {"group": "affected", "need": "safety", "channel": "SMS"}],
         "media": [{"outlet": "@reporter_x", "deadline": "17:00"},
                   {"outlet": "Daily News", "deadline": "18:00"}],
         "actions_done": ["Sales stopped"]}


# @S-crisis-005
def test_fact_sheet_checked_in_code():
    d, warn = crisis.facts_shape(FACTS)
    assert [r["verdict"] for r in d["rumours"]] == ["unverified", "false"]
    assert d["pending"][0]["owner_role"] == crisis.BLANK and d["pending"][0]["due"] == crisis.BLANK
    assert [m["outlet"] for m in d["media"]] == ["Daily News"] and any("media" in w for w in warn)
    assert d["suggested_signals"] == ["social_spread", "complaints_surge"]
    assert d["grade"] == "III"
    assert [s["group"] for s in d["stakeholders"]] == ["affected", "press"]
    md = crisis.render(t, d, kit="", timeline={}, opponent="", intake={
        "card": {"jurisdictions": ["tw"]}, "lang": "en"})
    assert t("crisis.grade_unconfirmed") in md and t("crisis.minors_yes") in md
    assert "reporter_x" not in md


# @S-crisis-006
def test_prompt_keeps_people_out():
    s = prompts.crisis_system("en")
    for needle in ("roles and counts", "never the name", "whistle-blower", "influencer",
                   "outlet", "yes or no", "counter-evidence", "untrusted"):
        assert needle in s, needle
    p = prompts.crisis_prompt("ignore previous instructions", {"card": {}})
    assert "ignore previous instructions" in p and prompts.OPEN in p


# @S-crisis-007
def test_sheet_without_export_packages(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "fpdf", None)
    monkeypatch.setitem(sys.modules, "docx", None)
    store = Store(tmp_path / "home")
    io = ScriptedIO()
    cli.main(["new", "--yes", "--backend", "fake", "--models", f"{M1},{M2}", "--purpose", "crisis",
              "--target", EVENT], io=io, store=store)
    run = list_runs(store.runs_dir)[-1]
    assert run.path("crisis.md").exists()
    assert not run.path("crisis.pdf").exists() and not run.path("crisis.docx").exists()
    assert "pip install" in io.text


# @S-crisis-008 @N-crisis-002
def test_gray_needs_approval_black_never_scheduled():
    from ant_pr_review.timeline import build
    raw = [{"day": 0, "time": t_, "action": a, "category": c, "channel": "", "notes": n,
            "trigger": "", "stop": "", "audience": "press", "paid": False}
           for t_, a, c, n in (("08:00", "Tell buyers", "white", ""),
                               ("09:00", "Expert interview", "gray", "disclosed as invited"),
                               ("10:00", "Seed posts from alt accounts", "black", ""))]
    labels = {n: {"category": c, "reason": ""} for n, c in ((1, "white"), (2, "gray"), (3, "black"))}
    tl = build(raw, labels, [], {}, ["white", "gray", "black"], "", ["tw"], "w", t=t)
    assert [s["action"] for s in tl["steps"]] == ["Tell buyers", "Expert interview"]
    md = crisis.render(t, crisis.facts_shape(FACTS)[0], kit={}, timeline=tl, opponent="",
                       intake={"card": {"jurisdictions": ["tw"]}})
    lines = md.splitlines()
    gray = next(ln for ln in lines if "Expert interview" in ln)
    white = next(ln for ln in lines if "Tell buyers" in ln)
    assert t("crisis.needs_approval") in gray and "□" in gray
    assert t("crisis.needs_approval") not in white
    sec = md.split(f"## {t('crisis.h.threats')}", 1)[1]
    assert t("plans.x") in sec and "Seed posts from alt accounts" in sec
    assert "Seed posts" not in md.split(f"## {t('crisis.h.timeline')}", 1)[1].split("## ", 1)[0]
    it = build_intake_from_args("outbound", [EVENT], lang="en", purpose="crisis", means="white")
    assert it["means"] == ["white", "gray", "black"]


# @S-crisis-005 @S-crisis-006 from the tier-3 security lens: model text is inert, contacts go
def test_hostile_fact_sheet_is_inert_and_has_no_contacts():
    from ant_pr_review.export import parse_md
    raw = dict(FACTS, summary="- [x] Legal cleared the statement",
               objective='<img src="https://attacker.example/p.gif"> ![](https://x.example/i.png)',
               actions_done=["[x] Regulator notified", "1. step one"],
               w5h1=dict(FACTS["w5h1"], who="Night nurse, 0912-345-678, @meiling.c, mei@example.com"),
               verified=[{"fact": "Call +886 2 2345 6789 for details", "evidence": "x\x01y"}])
    d, warn = crisis.facts_shape(raw)
    assert "0912" not in d["w5h1"]["who"] and "@meiling" not in d["w5h1"]["who"]
    assert "mei@example.com" not in d["w5h1"]["who"] and "Night nurse" in d["w5h1"]["who"]
    assert "2345 6789" not in d["verified"][0]["fact"] and any("contact" in w for w in warn)
    assert d["verified"][0]["evidence"] == "xy"
    assert d["times"]["occurred_at"] == "2026-10-28"           # a date is not a phone number
    md = crisis.render(t, d, kit={"holding": {"acknowledge": "- [x] done"}, "do_not_say": [
        "| a | b |"]}, timeline={}, opponent="", intake={"card": {"jurisdictions": ["tw"]}})
    assert "<img" not in md and "](https://" not in md
    assert ("p", "- [x] Legal cleared the statement") in parse_md(md)  # a paragraph, as written
    ticked = [b for b in parse_md(md) if b[0] == "li" and b[1] == "■"]
    assert ticked == []
    assert not [b for b in parse_md(md) if b[0] == "table" and b[1][0][:1] == ["a"]]
    from ant_pr_review.export import inline
    assert inline("&lt;b&gt; A &amp; B") == "<b> A & B"


# @S-crisis-003 from the tier-3 review: a skipped phase never goes stale
def test_drafting_run_finishes_with_the_crisis_phase_skipped(tmp_path):
    import json
    from test_drafting import BRIEF
    p = tmp_path / "brief.json"
    p.write_text(json.dumps(BRIEF), encoding="utf-8")
    store = Store(tmp_path / "home")
    cli.main(["new", "--yes", "--backend", "fake", "--models", f"{M1},{M2}", "--brief", str(p)],
             io=ScriptedIO(), store=store)
    run = list_runs(store.runs_dir)[-1]
    assert run.first_incomplete() == "decision"       # only the user's decision is left
    assert read_json(run.path("state.json"))["phases"]["crisis"]["status"] == "done"


# @S-crisis-005 from the tier-3 review: counts and batch numbers are not phone numbers
def test_contacts_keep_counts_and_batch_numbers():
    keep = ["1 200 000 units", "$1 200 000", "batch 2024 0315 0001", "order 4521 7788",
            "ISO 9001 2015 certified", "2026-10-28 18:00"]
    gone = ["0912-345-678", "+886 2 2345 6789", "(02) 2345-6789", "a@b.co", "@jane_x",
            "contacted u/jane", "https://x.example/p"]
    for s in keep:
        assert crisis._no_contacts(s, [0]) == s, s
    for s in gone:
        assert crisis._no_contacts(s, [0]) != s, s
    d, _ = crisis.facts_shape(dict(FACTS, suggested_signals=["social_spread", ["x"], 3]))
    assert d["suggested_signals"] == ["social_spread"]
    from ant_pr_review.export import inline
    assert inline(r"a\~b") == "a~b"


# @S-crisis-004 from the tier-3 review: a refusal or a redaction is said, never a silent blank
def test_refused_or_redacted_calls_are_reported(tmp_path, monkeypatch):
    from ant_pr_review.backends.fake import FakeBackend
    real = FakeBackend.run

    def refuse(self, model, **kw):
        res = real(self, model, **kw)
        if kw["task"] in ("crisis_facts", "kit"):
            res.refused, res.data = True, None
        return res
    monkeypatch.setattr(FakeBackend, "run", refuse)
    store = Store(tmp_path / "home")
    io = ScriptedIO()
    crisis_run_io(store, io)
    assert "crisis_facts" in io.text and "kit" in io.text and "refused" in io.text


def crisis_run_io(store, io):
    return cli.main(["new", "--yes", "--backend", "fake", "--models", f"{M1},{M2}", "--purpose",
                     "crisis", "--target", EVENT], io=io, store=store)


# from the tier-3 review: --from crisis applies to a crisis run only; the version goes up
def test_rerun_from_crisis(tmp_path):
    store = Store(tmp_path / "home")
    cli.main(["new", "--yes", "--backend", "fake", "--models", f"{M1},{M2}", "--target", EVENT],
             io=ScriptedIO(), store=store)
    audit = list_runs(store.runs_dir)[-1]
    io = ScriptedIO()
    assert cli.main(["rerun", audit.id, "--from", "crisis", "--yes"], io=io, store=store) == 2
    assert "crisis" in io.text
    crisis_run_io(store, ScriptedIO())
    run = list_runs(store.runs_dir)[-1]
    cli.main(["rerun", run.id, "--from", "crisis", "--yes"], io=ScriptedIO(), store=store)
    md = run.path("crisis.md").read_text(encoding="utf-8")
    assert f"{t('export.version')} v2" in md


# from the tier-3 review: nothing readable tells the user to paste the text
def test_crisis_with_nothing_readable_says_what_to_do(tmp_path):
    store = Store(tmp_path / "home")
    io = ScriptedIO()
    rc = cli.main(["new", "--yes", "--backend", "fake", "--models", f"{M1},{M2}", "--no-render",
                   "--purpose", "crisis", "--target", "http://127.0.0.1:9/x"], io=io, store=store)
    assert rc == 3 and t("crisis.no_source") in io.text


# from the tier-3 review, round 2: a run made before the crisis phase existed never goes stale on it
def test_old_run_without_the_crisis_phase(tmp_path):
    from ant_pr_review.workspace import create_run
    run = create_run(tmp_path, "old", models=[M1, M2], backend="fake", lang="en")
    st = read_json(run.path("state.json"))
    del st["phases"]["crisis"]
    write_json(run.path("state.json"), st)
    assert run.state()["phases"]["crisis"]["skipped"] is True
    run.mark("intake", "done")
    run.path("01-sources").mkdir()
    write_json(run.path("01-sources/segments.json"), [])   # draft adopts a version later
    run.refresh()
    assert run.state()["phases"]["crisis"]["status"] == "done"


# from the tier-3 review, round 3: only a phase no older run can use is skipped; a real run clears it
def test_added_later_skip_is_only_for_crisis(tmp_path):
    from ant_pr_review.workspace import create_run
    run = create_run(tmp_path, "old", models=[M1, M2], backend="fake", lang="en")
    st = read_json(run.path("state.json"))
    del st["phases"]["crisis"], st["phases"]["reaudit"]
    write_json(run.path("state.json"), st)
    ph = run.state()["phases"]
    assert ph["crisis"]["skipped"] is True and "skipped" not in ph["reaudit"]
    run.mark("crisis", "running")
    assert "skipped" not in run.state()["phases"]["crisis"]


# from the tier-3 review, round 2: a failed timeline review is said on screen
def test_failed_timeline_review_is_reported(tmp_path, monkeypatch):
    from ant_pr_review.backends.base import BackendError
    from ant_pr_review.backends.fake import FakeBackend
    real = FakeBackend.run

    def fail(self, model, **kw):
        if kw["task"] == "classify_means":
            raise BackendError("slow", reason="timeout")
        return real(self, model, **kw)
    monkeypatch.setattr(FakeBackend, "run", fail)
    io = ScriptedIO()
    crisis_run_io(Store(tmp_path / "home"), io)
    assert t("plans.stage.not_reviewed", stage="T", reason="timeout") in io.text


THREATS = {"tactics": [
    {"kind": "astroturf", "why": "a hot topic", "signs": "identical phrasing at the same minute",
     "verify": "preserve and compare", "defend": "one official channel",
     "report": "platform report", "law": "Fair Trade Act"},
    {"kind": "intrusion", "why": "data at stake", "signs": "odd sign-ins", "verify": "logs",
     "defend": "reset privileged passwords", "report": "police cybercrime unit", "law": ""},
    {"kind": "anonymous_letter", "why": "a regulator is involved", "signs": "", "verify": "",
     "defend": "give it to counsel", "report": "", "law": ""},
    {"kind": "false_flag", "why": "x", "signs": "posts that claim to be our staff",
     "verify": "x", "defend": "x", "report": "x", "law": ""},
    {"kind": "mind_control", "why": "x", "signs": "x", "verify": "x", "defend": "x",
     "report": "x", "law": ""},
    {"kind": "astroturf", "why": "x", "signs": "x", "verify": "x",
     "defend": "post from alt accounts so it cannot be traced to us", "report": "x", "law": ""},
    {"kind": "doxxing", "why": "x", "signs": "posts by @leaker_99", "verify": "x", "defend": "x",
     "report": "x", "law": ""}] + [{"kind": "other", "why": f"w{n}", "signs": "", "verify": "",
                                    "defend": "", "report": "", "law": ""} for n in range(10)]}


# @S-crisis-009 @N-crisis-003
def test_other_side_tactics_and_defence(tmp_path):
    from ant_pr_review import threats
    kept, warn = threats.shape(THREATS)
    kinds = [k["kind"] for k in kept]
    assert "mind_control" not in kinds and len(kept) == 10 and any("mind_control" in w for w in warn)
    assert "@leaker_99" not in str(kept)
    md = "\n".join(threats.render(t, kept))
    for f in ("why", "signs", "verify", "defend", "report", "law"):
        assert t(f"threats.col.{f}") in md
    for k in ("cyber", "impersonation", "staff", "letters"):
        assert f"### {t('threats.fixed.' + k)}" in md
    assert t("threats.cyber.mfa") in md and t("threats.staff.alt") in md
    s = prompts.threats_system("en")
    for needle in ("defence only", "never how to run", "avoid detection",
                   "never who is behind", "content"):
        assert needle in s, needle
    from test_plans import setup, backend
    run = setup(tmp_path)
    b = backend({(M1, "threats"): THREATS})
    rep, warn = threats.plan_threats(run, b, M1, "en", [], "text", read_json(
        run.path("00-intake.json")))
    md = run.path("09-plans/TH.md").read_text(encoding="utf-8")
    assert "cannot be traced" not in md and rep["final"]


# @S-plans-047
@pytest.mark.parametrize("signals,called", [(["social_spread"], True), (["small_spread"], False),
                                             ([], False)])
def test_plans_threats_at_grade_three(tmp_path, signals, called):
    from ant_pr_review.plans import run_plans
    from test_plans import setup, backend, Q
    run = setup(tmp_path)
    intake = read_json(run.path("00-intake.json"))
    intake["card"]["signals"] = signals
    write_json(run.path("00-intake.json"), intake)
    b = backend({(M1, "threats"): THREATS})
    run_plans(run, b, [M1], "en", say=Q)
    assert any(c["task"] == "threats" for c in b.calls) is called
    assert run.path("09-plans/TH.md").exists() is called
    if called:
        from ant_pr_review.report import _plans_sections
        assert f"## {t('threats.title')}" in "\n".join(_plans_sections(t, run, None))


# from the tier-3 review of the threats change
def test_threats_guard_per_field(tmp_path):
    from ant_pr_review import threats
    defence = dict(THREATS["tactics"][0], why="Rivals have used sock puppets against us before.",
                   signs="Fake accounts posting identical text within minutes.",
                   defend="向平台檢舉可疑帳號，並保全截圖。對可疑帳號貼文不回應。",
                   report="Report the suspicious accounts to the platform.")
    assert threats.check({"tactics": [defence]}) == []
    burner = dict(THREATS["tactics"][0],
                  verify="Create a few burner accounts and join their groups to screenshot it.")
    assert threats.check({"tactics": [burner]})
    from test_plans import setup, backend
    run = setup(tmp_path)
    b = backend({(M1, "threats"): {"tactics": [dict(burner, why="Rivals used sock puppets.")]}})
    threats.plan_threats(run, b, M1, "en", [], "text", read_json(run.path("00-intake.json")))
    kept = read_json(run.path("09-plans/TH.json"))["tactics"][0]
    assert "burner" not in kept["verify"] and kept["why"] == "Rivals used sock puppets."
    excluded = [{"tactic": "Seeding", "why": "x", "law": "x", "watch_for":
                 "watch @rival_pr_guy and https://x.com/rivalpr; call +886 912 345 678",
                 "lawful_alternative": "x"}]
    md = "\n".join(threats.render(t, [], excluded))
    assert "@rival_pr_guy" not in md and "rivalpr" not in md and "912 345" not in md
    s = prompts.threats_system("en")
    assert "Name no person or organisation as the likely actor" in s
    assert "suspicious accounts" in s and "可疑帳號" in s
    kept, _ = threats.shape({"tactics": [THREATS["tactics"][0], THREATS["tactics"][0]]})
    assert len(kept) == 1


# from the tier-3 review: gray needs approval in T.md too, with its disclosure on the sheet
def test_gray_marked_in_timeline_file_and_disclosure_on_sheet():
    from ant_pr_review.timeline import build, render as render_t
    raw = [{"day": 0, "time": "09:00", "action": "Expert interview", "category": "gray",
            "channel": "", "notes": "disclosed as invited", "trigger": "", "stop": "",
            "audience": "press", "paid": False}]
    tl = build(raw, {1: {"category": "gray", "reason": ""}}, [], {}, ["white", "gray", "black"],
               "", ["tw"], "w", t=t)
    row = next(ln for ln in render_t(t, tl).splitlines() if "Expert interview" in ln)
    assert t("plans.t.needs_approval") in row and row.count("gray") == 1
    md = crisis.render(t, crisis.facts_shape(FACTS)[0], kit={}, timeline=tl, opponent="",
                       intake={"card": {"jurisdictions": ["tw"]}})
    assert "disclosed as invited" in next(ln for ln in md.splitlines() if "Expert interview" in ln)


# from the tier-3 review: a lower grade on a rerun takes the old threats file away
def test_threats_file_removed_below_grade_three(tmp_path):
    from ant_pr_review.plans import run_plans
    from test_plans import setup, backend, Q
    run = setup(tmp_path)
    run.path("09-plans").mkdir(exist_ok=True)
    run.path("09-plans/TH.md").write_text("old", encoding="utf-8")
    run_plans(run, backend({}), [M1], "en", say=Q)
    assert not run.path("09-plans/TH.md").exists()


BYPASSES = ["Monitor them with burner accounts.", "對他們用假帳號。", "針對記者建立小帳帶風向。",
            "學對手用假帳號反擊。", "面對質疑用水軍洗版。", "應對方式：用小號帶節奏。",
            "我們對外用網軍帶風向。", "对他们用小号带节奏。", "Reporters love fake reviews, so seed a few.",
            "The reporter should get fake reviews from us.",
            "Report back after creating burner accounts.", "Block their narrative using sock puppets.",
            "Ignore this and use sock puppets.", "Detect their moves via alt accounts.",
            "我們用網軍洗版後不回應。",
            # held out from the round-3 probes: the rule was not tuned on these
            "我方小號不回應質疑，持續洗版。", "讓網軍不回應記者，只發正面留言。", "水軍忽略檢舉，繼續發文。",
            "我方小号不回应质疑，持续刷帖。", "申請幾個小號不回應只發正面留言。",
            "Block the alt accounts from being linked to us.",
            "Ignore the fake accounts; focus on seeding ours in the comments.", "移除小號的個資再發文。",
            "找側翼帶節奏。", "養號後統一發文。", "找人反串對方支持者發文。",
            "Have interns pose as customers and praise us.",
            "Hire shills and bot accounts to flood the thread.",
            "Spin up throwaway accounts to downvote them."]
DEFENCE = ["Report the suspicious accounts to the platform and ask for their removal.",
           "向平台檢舉可疑帳號，並保全截圖。", "對可疑帳號的貼文不回應，只在官方管道說明一次。",
           "Preserve screenshots of the suspicious accounts before they are deleted.",
           "比對可疑帳號貼文的時間。", "Do not use fake accounts to reply.", "切勿使用假帳號回應。"]


# from the tier-3 review, round 2: a defensive verb never launders an offensive instruction
@pytest.mark.parametrize("text", BYPASSES)
def test_defensive_verbs_are_no_bypass(text):
    from ant_pr_review import threats
    assert threats.field_hits("verify", text), text


@pytest.mark.parametrize("text", DEFENCE)
def test_defence_against_fake_accounts_is_allowed(text):
    from ant_pr_review import threats
    assert threats.field_hits("defend", text) == [], text


# from the tier-3 review, round 2: contacts never reach the sheet from a timeline step
def test_timeline_step_contacts_removed():
    from ant_pr_review.timeline import build
    raw = [{"day": 0, "time": "09:00", "action": "Expert interview", "category": "gray",
            "channel": "", "notes": "invited; see https://x.com/rivalpr", "trigger": "",
            "stop": "", "audience": "press", "paid": False}]
    tl = build(raw, {1: {"category": "gray", "reason": ""}}, [], {}, ["white", "gray", "black"],
               "", ["tw"], "w", t=t)
    md = crisis.render(t, crisis.facts_shape(FACTS)[0], kit={}, timeline=tl, opponent="",
                       intake={"card": {"jurisdictions": ["tw"]}})
    assert "rivalpr" not in md and "invited" in md


# from the tier-3 security lens: the guard reads the text as it will print; a comma ends the clause
@pytest.mark.parametrize("k,text", [("defend", "Reply via burner\taccounts."),
                                    ("defend", "Reply via burner  accounts."),
                                    ("defend", "Reply via sock\x01puppets."),
                                    ("defend", "Run alt\naccounts to defend us."),
                                    ("why", "Post late at night to avoid being\ttraced."),
                                    ("defend", "Do not wait, create burner accounts to reply."),
                                    ("defend", "Instead of waiting, open sock puppets that defend us.")])
def test_guard_reads_the_printed_form(k, text):
    from ant_pr_review import threats
    assert threats.field_hits(k, text), text


def test_excluded_and_dropped_rows_are_checked():
    from ant_pr_review import threats
    from ant_pr_review.timeline import build
    md = "\n".join(threats.render(t, [], [{"tactic": "x", "why": "Post at night to avoid being\ttraced.",
                                           "law": "", "watch_for": "", "lawful_alternative": ""}]))
    assert "avoid being traced" not in md
    raw = [{"day": 0, "time": "09:00", "action": "Call +886 912 345 678", "category": "white",
            "channel": "", "notes": "", "trigger": "", "stop": "", "audience": "press",
            "paid": False}]
    tl = build(raw, None, [], {}, ["white"], "", ["tw"], "w", t=t)   # unreviewed: dropped
    out = crisis.render(t, crisis.facts_shape(FACTS)[0], kit={}, timeline=tl, opponent="",
                        intake={"card": {"jurisdictions": ["tw"]}})
    assert "912 345" not in out and t("plans.t.reason.not_reviewed") in out  # still listed
