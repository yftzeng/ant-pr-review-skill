from ant_pr_review.decision import run_decision
from ant_pr_review.jsonio import append_jsonl, read_json, write_json, write_text_atomic
from ant_pr_review.refresh import compute_synthesis
from ant_pr_review.report import latest_version, write_report
from ant_pr_review.review import run_round1
from ant_pr_review.store import DEFAULT_THRESHOLDS, Store
from ant_pr_review.ui import ScriptedIO
from helpers import M1, M2, ScriptBackend, auto_review, make_run

M = [M1, M2]


def setup(tmp_path, flags1=(), flags2=(), org=None, corrections=(), js=("tw",)):
    run = make_run(tmp_path, jurisdictions=js, lenses=["legal"],
                   card={"org": org} if org else None)
    run_round1(run, ScriptBackend({(M1, "review"): auto_review(flags=list(flags1)),
                                   (M2, "review"): auto_review(flags=list(flags2))}),
               M, "en", say=lambda *_: None)
    write_report(run, compute_synthesis(run, M, DEFAULT_THRESHOLDS), lang="en")
    write_text_atomic(run.path("09-plans/A.md"), "A text\n")
    write_text_atomic(run.path("09-plans/B.md"), "B text\n")
    write_json(run.path("09-plans/B.json"), {"recommendation": "publish_revised"})
    write_json(run.path("09-plans/corrections.json"), list(corrections))
    return run, Store(tmp_path / "home")


def decide(run, store, io=None, **kw):
    return run_decision(io, run, store, models=M, lang="en", thresholds=DEFAULT_THRESHOLDS,
                        min_repeats=3, **kw)


# @S-decision-001
def test_ruling_per_jurisdiction_and_new_report(tmp_path):
    run, store = setup(tmp_path, flags1=["election_law"])
    io = ScriptedIO(["2", "2"])  # dismiss, then choose B
    decide(run, store, io)
    assert "Taiwan · Election law" in io.text
    assert read_json(run.path("10-decision.json"))["rulings"] == {"tw:election_law": "dismissed"}
    assert latest_version(run) == 2 and "Dismissed" in run.path("08-report.v2.md").read_text()


# @S-decision-002
def test_choice_becomes_final(tmp_path):
    run, store = setup(tmp_path)
    decide(run, store, ScriptedIO(["2"]))
    assert run.path("final.md").read_text() == "B text\n"
    assert read_json(run.path("10-decision.json"))["choice"] == "B"


ACME = [{"from": "Acme Corp", "to": "ACME", "category": "name"}]


def _seed(store):
    for r in ("old-1", "old-2"):
        append_jsonl(store.corrections_log, {"brand": "acme", "run": r, "from": "Acme Corp",
                                             "to": "ACME", "category": "name"})


# @S-decision-003
def test_recurring_correction_proposed_and_written(tmp_path):
    run, store = setup(tmp_path, org="acme", corrections=ACME)
    _seed(store)
    decide(run, store, ScriptedIO(["1", "y"]))
    assert '"Acme Corp" -> "ACME"' in (store.style_guides / "acme.md").read_text()


# @S-decision-004 @N-decision-001
def test_declined_proposal_writes_nothing(tmp_path):
    run, store = setup(tmp_path, org="acme", corrections=ACME)
    _seed(store)
    io = ScriptedIO(["1", "n"])
    decide(run, store, io)
    assert "Style Guide" in io.text and not (store.style_guides / "acme.md").exists()


# @S-decision-005
def test_non_interactive_bare_key_applies_everywhere(tmp_path):
    run, store = setup(tmp_path, flags1=["election_law"], js=("tw", "us"))
    dec = decide(run, store, None, choice="A", rulings={"election_law": "confirmed"})
    assert dec["choice"] == "A"
    assert dec["rulings"] == {"tw:election_law": "confirmed", "us:election_law": "confirmed"}
    syn = read_json(run.path("06-synthesis.json"))
    assert syn["consolidated"]["verdict"] == "no_go"
    assert run.path("final.md").read_text() == "A text\n"


# @S-decision-007
def test_hold_is_default_for_no_go_and_writes_no_final(tmp_path):
    run, store = setup(tmp_path, flags1=["undisclosed_inauthentic"],
                       flags2=["undisclosed_inauthentic"])
    assert read_json(run.path("06-synthesis.json"))["consolidated"]["verdict"] == "no_go"
    io = ScriptedIO([""])
    dec = decide(run, store, io)
    assert dec["choice"] == "hold" and not run.path("final.md").exists()
    assert read_json(run.path("10-decision.json"))["choice"] == "hold"
