from ant_pr_review.backends.base import BackendError, Result
from ant_pr_review.factcheck import (build_ledger, check_claim, is_retryable, read_ledger,
                                       run_checks, snapshot, write_ledger)
from ant_pr_review.refresh import compute_synthesis, factcheck_continue
from ant_pr_review.report import latest_version, write_report
from ant_pr_review.ui import ScriptedIO
from ant_pr_review.review import run_round1
from ant_pr_review.store import DEFAULT_THRESHOLDS as TH
from helpers import M1, M2, ScriptBackend, auto_review, make_run, recs, review_data

MS = [M1, M2]
CLAIM = {"id": "C01", "anchor": "D1.P02.S1", "text": "Revenue grew 40% in 2025",
         "type": "number", "status": "pending", "reason": "", "sources": [], "refs": []}


def search_result(status, urls, seen):
    return Result(model="", model_id="", data={
        "status": status, "reason": "r",
        "sources": [{"url": u, "supporting_excerpt": "e"} for u in urls]},
        tool_calls=[{"name": "WebSearch", "input": {"query": "q"}}],
        tool_results=["Links: " + " ".join(seen)])


# @S-factcheck-ledger-001
def test_ledger_merges_claims():
    reviews = recs(("tw.legal", M1, review_data(claims=[{}])),
                   ("global.all", M2, review_data(claims=[{}, {"id": "K2", "anchor": "D1.P03.S1",
                                                               "text": "“We lead”, said Ann",
                                                               "type": "quote"}])))
    led = build_ledger(reviews, [])
    assert len(led) == 2
    assert sorted(led[0]["extracted_by"]) == sorted([M1, M2])
    assert sorted(led[0]["refs"]) == ["global.all/openai_gpt-5:K1", "tw.legal/claude_opus:K1"]
    assert {c["status"] for c in led} == {"pending"}


# @S-factcheck-ledger-002
def test_source_not_in_search_results_dropped():
    b = ScriptBackend({("sonnet", "factcheck"): search_result(
        "supported", ["https://a.example/x", "https://b.example/y"], ["https://a.example/x"])})
    c = check_claim(b, "sonnet", CLAIM, "ctx", "en")
    assert c["status"] == "supported" and [s["url"] for s in c["sources"]] == ["https://a.example/x"]
    assert b.calls[0]["tools"] == ("WebSearch", "WebFetch")


# @S-factcheck-ledger-003
# @N-factcheck-ledger-001
def test_no_search_means_cannot_verify():
    b = ScriptBackend({("sonnet", "factcheck"): Result(model="", model_id="", data={
        "status": "supported", "reason": "", "sources": [{"url": "https://w.example",
                                                          "supporting_excerpt": "e"}]})})
    c = check_claim(b, "sonnet", CLAIM, "ctx", "en")
    assert (c["status"], c["reason"]) == ("cannot_verify", "no_search")
    b2 = ScriptBackend({("sonnet", "factcheck"): search_result("unsupported",
                                                               ["https://x.example"], [])})
    c2 = check_claim(b2, "sonnet", CLAIM, "ctx", "en")
    assert (c2["status"], c2["reason"]) == ("cannot_verify", "no_source")


# @S-factcheck-ledger-004
def test_offline_timeout_retryable():
    b = ScriptBackend({("sonnet", "factcheck"): BackendError("x", reason="offline")})
    c1 = check_claim(b, "sonnet", CLAIM, "", "en")
    b.handlers[("sonnet", "factcheck")] = BackendError("x", reason="timeout")
    c2 = check_claim(b, "sonnet", dict(CLAIM, id="C02"), "", "en")
    assert (c1["status"], c1["reason"]) == ("cannot_verify", "offline")
    assert (c2["status"], c2["reason"]) == ("cannot_verify", "timeout")
    assert is_retryable(c1) and is_retryable(c2)


# @S-factcheck-ledger-005
def test_continue_checks_only_retryable(tmp_path):
    run = make_run(tmp_path)
    write_ledger(run, [dict(CLAIM, id="C01", status="supported"),
                       dict(CLAIM, id="C02", status="cannot_verify", reason="offline"),
                       dict(CLAIM, id="C03", status="cannot_verify", reason="no_source")])
    b = ScriptBackend({("sonnet", "factcheck"): search_result("supported", ["https://a.example"],
                                                              ["https://a.example"])})
    run_checks(run, b, "sonnet", "en", say=lambda *_: None)
    assert len(b.calls) == 1 and "C02" not in b.calls[0]["prompt"]  # prompt has claim text
    assert [c["status"] for c in read_ledger(run)] == ["supported", "supported", "cannot_verify"]


def _setup_reported(tmp_path, ledger):
    run = make_run(tmp_path, lenses=["legal"])
    run_round1(run, ScriptBackend({(M1, "review"): auto_review(flags=["fabrication_about_party"]),
                                   (M2, "review"): auto_review()}), MS, "en", say=lambda *_: None)
    write_ledger(run, ledger)
    write_report(run, compute_synthesis(run, MS, TH), lang="en")
    return run


# @S-factcheck-ledger-006
def test_unfinished_continue_offers_choices(tmp_path):
    led = [dict(CLAIM, id=f"C{i:02d}", status="supported") for i in range(1, 19)]
    led += [dict(CLAIM, id=f"C{i:02d}", status="pending") for i in range(19, 31)]
    run = _setup_reported(tmp_path, led)
    fails = iter([BackendError("x", reason="offline")] * 9 + [BackendError("x", reason="timeout")] * 3)
    b = ScriptBackend({("*", "factcheck"): lambda p: next(fails)})
    io = ScriptedIO(["1"])
    assert factcheck_continue(run, b, MS, TH, "en", io) == "later"
    assert "18/30" in io.text and "offline 9" in io.text and "timeout 3" in io.text
    assert "Continue another time" in io.text and "Stop and finalize" in io.text
    assert f"factcheck {run.id} --continue" in io.text


# @S-factcheck-ledger-007
def test_finalize_unchanged(tmp_path):
    run = _setup_reported(tmp_path, [dict(CLAIM, status="cannot_verify", reason="no_source")])
    io = ScriptedIO([])
    assert factcheck_continue(run, ScriptBackend(), MS, TH, "en", io) == "unchanged"
    assert "unchanged" in io.text and latest_version(run) == 1


# @S-factcheck-ledger-008
def test_finalize_changed_writes_v2(tmp_path):
    run = _setup_reported(tmp_path, [dict(CLAIM, id="C02", type="allegation",
                                          status="cannot_verify", reason="offline")])
    b = ScriptBackend({("*", "factcheck"): search_result("unsupported", ["https://a.example/n"],
                                                         ["https://a.example/n"])})
    io = ScriptedIO([])
    assert factcheck_continue(run, b, MS, TH, "en", io) == "updated"
    assert [c["task"] for c in b.calls] == ["factcheck"]
    md = run.path("08-report.v2.md").read_text()
    assert "C02: cannot_verify -> unsupported" in md
    assert "tw red line fabrication_about_party: needs_ruling -> confirmed" in md
    assert "tw verdict: go -> no_go" in md


# @S-factcheck-ledger-009
def test_law_citations_and_allegations_are_claims():
    from ant_pr_review.prompts import factcheck_system
    reviews = recs(("tw.legal", M1, review_data(claims=[
        {"id": "K1", "text": "Fair Trade Act art. 24 bans disparaging false statements",
         "type": "legal_citation"},
        {"id": "K2", "anchor": "D1.P03.S1", "text": "A's phones exploded", "type": "allegation"}])))
    led = build_ledger(reviews, [])
    assert [(c["type"], c["status"]) for c in led] == [("legal_citation", "pending"),
                                                      ("allegation", "pending")]
    assert "official law database" in factcheck_system("en")


def test_snapshot_changes_with_status():
    a = [dict(CLAIM)]
    b = [dict(CLAIM, status="supported")]
    assert snapshot(a) != snapshot(b)
