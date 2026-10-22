import json

from ant_pr_review.backends.base import Result
from ant_pr_review.backends.fake import FakeBackend
from ant_pr_review.cli import main
from ant_pr_review.contextscan import run_queries
from ant_pr_review.factcheck import read_ledger, run_checks, write_ledger
from ant_pr_review.jsonio import read_json
from ant_pr_review.pipeline import Ctx, ph_context
from ant_pr_review.store import Config, Store
from ant_pr_review.ui import ScriptedIO
from ant_pr_review.workspace import list_runs
from helpers import M1, M2, ScriptBackend, make_run

TEXT = "# Launch\n\nOur phone is the best in Taiwan.\n\nAcme's phones exploded last year."


class Recording(FakeBackend):
    def __init__(self):
        self.calls = []

    def run(self, model, **kw):
        self.calls.append((model, kw["task"], tuple(kw.get("tools") or ())))
        return super().run(model, **kw)


def run_cli(tmp_path, monkeypatch, *args):
    rec = Recording()
    monkeypatch.setattr("ant_pr_review.cli.get_backend", lambda name: rec)
    store = Store(tmp_path / "home")
    io = ScriptedIO([])
    rc = main(list(args), io=io, store=store)
    return rc, io, store, rec


def ctx(run, models, answers=(), interactive=True, **options):
    return Ctx(io=ScriptedIO(list(answers)), store=None, cfg=Config(), backend=None,
               models=list(models), lang="en", interactive=interactive, options=options)


# @S-context-scan-001 @N-context-scan-001
def test_embargo_keeps_everything_offline(tmp_path, monkeypatch):
    rc, io, store, rec = run_cli(tmp_path, monkeypatch, "new", "--yes", "--backend", "fake",
                                 "--embargo", "--context-scan", "--party", "Acme",
                                 "--target", TEXT)
    assert rc == 3 and rec.calls
    assert all(tools == () for _, _, tools in rec.calls)
    run = list_runs(store.runs_dir)[0]
    assert read_json(run.path("02-context.json"))["status"] == "embargo"
    ledger = read_ledger(run)
    assert ledger and all(c["status"] == "cannot_verify" and c["reason"] == "embargo"
                          for c in ledger)


# @S-context-scan-002
def test_queries_shown_and_run_only_after_confirmation(tmp_path):
    run = make_run(tmp_path, card={"parties": ["Acme"]})
    c = ctx(run, [M1, M2], answers=["n"])
    c.backend = ScriptBackend({("*", "context"): {"findings": []}})
    ph_context(run, c)
    assert "Acme latest news controversy" in c.io.text and c.backend.calls == []
    assert read_json(run.path("02-context.json"))["status"] == "skipped"
    c = ctx(run, [M1, M2], answers=["y"])
    c.backend = ScriptBackend({("*", "context"): {"findings": []}})
    ph_context(run, c)
    assert [x["model"] for x in c.backend.calls] == [M1, M1]
    assert all(x["tools"] == ("WebSearch",) for x in c.backend.calls)
    assert read_json(run.path("02-context.json"))["status"] == "done"


# @S-context-scan-003
def test_non_interactive_needs_the_flag(tmp_path):
    run = make_run(tmp_path, card={"parties": ["Acme"]})
    c = ctx(run, [M1, M2], interactive=False)
    c.backend = ScriptBackend({("*", "context"): {"findings": []}})
    ph_context(run, c)
    assert c.backend.calls == [] and read_json(run.path("02-context.json"))["status"] == "skipped"


# @S-context-scan-004
def test_finding_without_searched_url_is_dropped():
    res = Result(model="", model_id="", data={"findings": [
        {"summary": "real", "url": "https://news.example/a", "date": "", "relevance": "high"},
        {"summary": "made up", "url": "https://made.up/b", "date": "", "relevance": "high"}]},
        tool_calls=[{"name": "WebSearch"}], tool_results=["https://news.example/a"])
    found, errors = run_queries(ScriptBackend({(M1, "context"): res}), M1, ["q"], "en",
                                say=lambda *_: None)
    assert [f["summary"] for f in found] == ["real"]
    assert "1 finding(s) without a searched source dropped" in errors[0]


# @S-context-scan-005
def test_without_claude_nothing_is_searched(tmp_path):
    models = ["openai:gpt-5", "gemini:gemini-2.5-pro"]
    run = make_run(tmp_path, models=models, card={"parties": ["Acme"]})
    c = ctx(run, models, context_scan=True)
    c.backend = ScriptBackend({})
    ph_context(run, c)
    assert read_json(run.path("02-context.json"))["status"] == "no_search_backend"
    write_ledger(run, [{"id": "C01", "anchor": "D1.P01", "text": "t", "type": "allegation",
                        "status": "pending", "reason": "", "sources": [], "refs": []}])
    b = ScriptBackend({})
    run_checks(run, b, None, "en", say=lambda *_: None)
    assert b.calls == [] and read_ledger(run)[0]["reason"] == "no_search_backend"


# @S-context-scan-006
def test_lifting_the_embargo_lets_factcheck_run(tmp_path, monkeypatch):
    rc, io, store, rec = run_cli(tmp_path, monkeypatch, "new", "--yes", "--backend", "fake",
                                 "--embargo", "--target", TEXT)
    run = list_runs(store.runs_dir)[0]
    rc, io, _, rec = run_cli(tmp_path, monkeypatch, "factcheck", run.id, "--continue",
                             "--lift-embargo", "--yes", "--finalize", "--backend", "fake")
    assert rc == 0 and any(tools for _, task, tools in rec.calls if task == "factcheck")
    assert all(c["status"] == "supported" for c in read_ledger(run))
    assert run.path("08-report.v2.md").exists()
    assert json.loads(run.path("08-report.v2.json").read_text())["version"] == 2
