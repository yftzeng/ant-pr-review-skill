import pytest

import ant_pr_review.cli as cli
from ant_pr_review.backends.base import BackendError
from ant_pr_review.backends.fake import FakeBackend
from ant_pr_review.jsonio import read_json
from ant_pr_review.store import Store
from ant_pr_review.ui import ScriptedIO
from ant_pr_review.workspace import PHASES, list_runs

TEXT = "# Post\n\nOur product is great. It grew 40% last year.\n\nBuy now."


class CountingFake(FakeBackend):
    calls = []

    def run(self, model, *, task, **kw):
        CountingFake.calls.append((model, task))
        return super().run(model, task=task, **kw)


class NoAskIO(ScriptedIO):
    def ask(self, prompt):
        raise AssertionError(f"prompted in non-interactive mode: {prompt}")


@pytest.fixture
def env(tmp_path, monkeypatch):
    CountingFake.calls = []
    monkeypatch.setattr(cli, "get_backend", lambda name: CountingFake())
    return Store(tmp_path / "home")


def new_run(store, io=None):
    io = io or NoAskIO()
    code = cli.main(["new", "--yes", "--backend", "fake", "--target", TEXT], io=io, store=store)
    return code, io, list_runs(store.runs_dir)[-1]


# @S-cli-001
# @N-cli-001
def test_non_interactive_to_decision_gate(env):
    code, io, run = new_run(env)
    assert code == 3
    assert run.path("08-report.v1.md").exists() and run.path("09-plans/A.md").exists()
    assert run.status("decision") == "pending"
    assert "Reviewers: claude:opus [anthropic], claude:sonnet [anthropic]" in io.text
    assert f"ant-pr-review decide {run.id}" in io.text


# @S-cli-002
def test_decide_then_resume(env):
    _, _, run = new_run(env)
    CountingFake.calls = []
    assert cli.main(["decide", run.id, "--yes", "--choice", "A"], io=NoAskIO(), store=env) == 0
    assert cli.main(["resume", run.id, "--yes"], io=NoAskIO(), store=env) == 0
    assert run.path("final.md").read_text() == run.path("09-plans/A.md").read_text()
    assert all(run.status(p) == "done" for p in PHASES)
    assert CountingFake.calls == []


# @S-cli-003
def test_rerun_from_review(env):
    _, _, run = new_run(env)
    cli.main(["decide", run.id, "--yes", "--choice", "A"], io=NoAskIO(), store=env)
    CountingFake.calls = []
    cli.main(["rerun", run.id, "--from", "review", "--yes"], io=NoAskIO(), store=env)
    assert {m for m, t in CountingFake.calls if t == "review"} == {"claude:opus", "claude:sonnet"}
    assert len([1 for m, t in CountingFake.calls if t == "review"]) == 4  # 2 units x 2 models
    assert run.path("08-report.v2.md").exists()


# @S-cli-004
def test_unfinished_run_offered(env):
    _, _, run = new_run(env)
    io = ScriptedIO([])
    cli.main([], io=io, store=env)
    assert f"Continue {run.id} from phase decision" in io.text


# @S-cli-005
def test_ctrl_c_leaves_resumable(env, monkeypatch):
    class Boom(CountingFake):
        def run(self, model, *, task, **kw):
            if task == "review":
                raise KeyboardInterrupt
            return super().run(model, task=task, **kw)
    monkeypatch.setattr(cli, "get_backend", lambda name: Boom())
    io = NoAskIO()
    code = cli.main(["new", "--yes", "--target", TEXT], io=io, store=env)
    run = list_runs(env.runs_dir)[-1]
    assert code == 130 and run.status("review") == "pending"
    assert f"ant-pr-review resume {run.id}" in io.text


# @S-cli-006
def test_backend_failure_pauses(env, monkeypatch):
    class Down(CountingFake):
        def run(self, model, *, task, **kw):
            raise BackendError("down", reason="offline")
    monkeypatch.setattr(cli, "get_backend", lambda name: Down())
    code = cli.main(["new", "--yes", "--target", TEXT], io=NoAskIO(), store=env)
    run = list_runs(env.runs_dir)[-1]
    assert code == 3
    assert run.status("sources") == "done" and run.status("matrix") == "done"
    assert run.status("review") == "pending"
    assert read_json(run.path("04-reviews/global.all/claude_opus.json"))["reason"] == "offline"


# @S-cli-007
def test_runs_lists_next_phase(env):
    _, _, run = new_run(env)
    io = NoAskIO()
    cli.main(["runs", "--yes"], io=io, store=env)
    line = [ln for ln in io.text.splitlines() if run.id in ln][0]
    assert "outbound" in line and "next: decision" in line


def test_models_override_recorded_in_run(env):
    cli.main(["new", "--yes", "--models", "opus,openai:gpt-5", "--target", TEXT], io=NoAskIO(),
             store=env)
    run = list_runs(env.runs_dir)[-1]
    assert run.settings()[0] == ["claude:opus", "openai:gpt-5"]
    assert env.load_config().models == ["claude:opus", "claude:sonnet"]


# @S-cli-008
def test_slug_from_target(env):
    from ant_pr_review.cli import slug_for
    from ant_pr_review.workspace import slugify
    assert slugify(slug_for("/tmp/x/my-article.md")) == "my-article"
    assert slugify(slug_for("https://example.com/blog/hello-world")) == "example-com-hello-world"
    assert slugify(slug_for("# Big News\nBody")) == "big-news"


# @S-cli-009
def test_abandoned_intake_leaves_no_run(env):
    env.save_config(__import__("ant_pr_review.store", fromlist=["Config"]).Config())
    io = ScriptedIO(["2", "https://example.com/a", "/done", "Acme"])  # audit; input ends in the card
    code = cli.main([], io=io, store=env)
    assert code == 130
    assert list_runs(env.runs_dir) == []


# @S-cli-010
def test_delete_unfinished_run_from_menu(env):
    from ant_pr_review.workspace import create_run
    run = create_run(env.runs_dir, "run", models=["claude:opus", "claude:sonnet"], backend="fake",
                     lang="en")
    env.save_config(__import__("ant_pr_review.store", fromlist=["Config"]).Config())
    # menu: 1) continue run  2) delete an unfinished run  3) new ; then pick run 1, decline
    io = ScriptedIO(["2", "1", "n"])
    cli.main([], io=io, store=env)
    assert run.root.exists() and "1 file" in io.text
    io = ScriptedIO(["2", "1", "y"])
    cli.main([], io=io, store=env)
    assert not run.root.exists()


# @S-cli-013
def test_runs_summary(env, tmp_path):
    import csv
    from ant_pr_review.jsonio import write_json
    from ant_pr_review.workspace import create_run
    for slug, verdict, red in (("first", "conditional", {}),
                               ("second", "no_go", {"undisclosed_inauthentic": "confirmed"})):
        r = create_run(env.runs_dir, slug, models=["claude:opus", "claude:sonnet"],
                       backend="fake", lang="en")
        write_json(r.path("00-intake.json"), {"direction": "outbound", "targets": [
            {"kind": "text", "value": f"# {slug.title()} Post\n\nbody"}], "card": {}})
        write_json(r.path("08-report.v1.json"), {
            "version": 1, "verdict": verdict, "risks": 3,
            "red_lines": {"tw": dict({"election_law": "clear"}, **red)}})
    create_run(env.runs_dir, "empty", models=["claude:opus", "claude:sonnet"], backend="fake",
               lang="en")
    io = NoAskIO()
    cli.main(["runs", "--yes", "--summary"], io=io, store=env)
    rows = [ln for ln in io.text.splitlines() if ln.startswith("| 20")]
    assert len(rows) == 3
    first = [ln for ln in rows if "First Post" in ln][0]
    assert "conditional" in first and "outbound" in first and "| 3 |" in first
    assert "tw:undisclosed_inauthentic" in [ln for ln in rows if "Second Post" in ln][0]
    out = tmp_path / "summary.csv"
    cli.main(["runs", "--yes", "--summary", "--format", "csv", "--out", str(out)], io=NoAskIO(),
             store=env)
    data = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(data) == 3 and {"run", "title", "direction", "verdict", "red_lines", "risks",
                               "next"} <= set(data[0])


# @S-cli-014
def test_several_jurisdictions_in_one_run(env):
    code = cli.main(["new", "--yes", "--backend", "fake", "--jurisdictions", "tw,us",
                     "--depth", "full", "--target", TEXT], io=NoAskIO(), store=env)
    run = list_runs(env.runs_dir)[-1]
    assert code == 3
    units = [u["id"] for u in read_json(run.path("03-matrix.json"))["units"]]
    assert "tw.legal" in units and "us.legal" in units and "global.journalist" in units
    assert read_json(run.path("07-jmerge/final.json"))["status"] == "ok"
    for f in ("08-report.v1.md", "08-report.v1.tw.md", "08-report.v1.us.md"):
        assert run.path(f).exists(), f
    tasks = {t for _, t in CountingFake.calls}
    assert {"jcompare", "jdiscuss", "jfinal"} <= tasks
