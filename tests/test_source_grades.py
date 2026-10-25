"""Graded fact-check sources (S-factcheck-ledger-014) and graded veto evidence
(S-review-matrix-033)."""
from ant_pr_review.backends.base import Result
from ant_pr_review.factcheck import check_claim
from ant_pr_review.i18n import T
from ant_pr_review.report import ledger_status, source_urls
from ant_pr_review.sources.grade import grade_source, is_evidence, strength
from helpers import M1, M2, ScriptBackend, deb, recs, review_data
from test_factcheck import CLAIM
from test_review_matrix import ITEMS, U, synth

t = T("en")


def src(url, kind=None):
    return {"url": url, **({"kind": kind} if kind else {}),
            **({"grade": grade_source(url, kind)} if kind else {})}


# @S-factcheck-ledger-014
def test_grades_and_strength():
    assert grade_source("https://law.moj.gov.tw/LawClass/x", "law_database") == "A"
    assert grade_source("https://regulator-news.blogspot.com/x", "regulator") == "C"
    assert grade_source("https://news.example.com/a", "independent") == "B"
    assert grade_source("https://www.acme.com/about", "company_claim") == "C"
    assert grade_source("https://forum.example.net/t/1", "lead") == "C"
    assert grade_source("https://doi.org/10.1/x", "academic") == "A"
    assert grade_source("https://arxiv.org/abs/1706.03762", "academic") == "A"
    assert grade_source("https://www.nature.com/articles/x", "academic") == "B"
    assert grade_source("https://news.example.com/a", None) == ""
    assert grade_source("https://news.example.com/a", "made_up") == ""
    a = src("https://law.moj.gov.tw/x", "law_database")
    b1, b2 = src("https://news.example.com/a", "independent"), src("https://other.tw/b", "independent")
    b1_again = src("https://www.example.com/c", "independent")  # same outlet as b1
    c = src("https://forum.example.net/t/1", "lead")
    assert strength([a]) == "strong" and strength([b1, b2]) == "strong"
    assert strength([b1, b1_again]) == "single" and strength([b1, c]) == "single"
    assert strength([c, c]) == "weak"
    assert strength([{"url": "https://x.example/1"}]) == "ungraded"
    assert strength([]) == ""
    assert is_evidence({"sources": [a]}) and is_evidence({"sources": [b1]})
    assert is_evidence({"sources": [{"url": "https://x.example/1"}]})   # legacy ledger
    assert not is_evidence({"sources": [c]})


# @S-factcheck-ledger-014 the checker names the kind, code grades it
def test_check_claim_grades_kept_sources():
    urls = ["https://law.moj.gov.tw/x", "https://fake-gov.blogspot.com/y", "https://news.example.com/z"]
    res = Result(model="", model_id="", data={"status": "supported", "reason": "r", "sources": [
        {"url": urls[0], "supporting_excerpt": "e", "kind": "law_database"},
        {"url": urls[1], "supporting_excerpt": "e", "kind": "regulator"},
        {"url": urls[2], "supporting_excerpt": "e", "kind": "independent"}]},
        tool_calls=[{"name": "WebSearch", "input": {"query": "q"}}],
        tool_results=["Links: " + " ".join(urls)])
    c = check_claim(ScriptBackend({(M1, "factcheck"): res}), M1, CLAIM, "ctx", "en")
    assert [s["grade"] for s in c["sources"]] == ["A", "C", "B"]
    assert c["strength"] == "strong"
    from ant_pr_review import prompts
    s = prompts.factcheck_system("en")
    for k in ("law_database", "regulator", "independent", "company_claim", "lead"):
        assert k in s, k
    from ant_pr_review.schemas import FACTCHECK
    assert "kind" in FACTCHECK["properties"]["sources"]["items"]["required"]


# @S-factcheck-ledger-014 the report shows grades and strength
def test_report_shows_grade_and_strength():
    s = src("https://law.moj.gov.tw/x", "law_database")
    assert "[A]" in source_urls([dict(s, accessed_at="2026-10-26T10:00:00")])
    assert "[" not in source_urls([{"url": "https://x.example/1"}])
    c = {"status": "supported", "reason": "", "strength": "weak"}
    assert t("strength.weak") in ledger_status(t, c)
    assert ledger_status(t, {"status": "cannot_verify", "reason": "no_source"}) == \
        "cannot_verify (no_source)"
    for lang in ("zh-TW", "zh-CN"):
        assert T(lang)("strength.weak") not in ("strength.weak", t("strength.weak"))


# @S-review-matrix-033
def test_only_graded_evidence_outranks_a_dispute():
    key = "fabrication_about_party"
    r = recs((U, M1, review_data(items=ITEMS, flags=[key])), (U, M2, review_data(items=ITEMS)))
    dispute = deb(M2, U, {"target": f"claude_opus:redline:{key}", "position": "dispute",
                          "evidence": "x"})

    def claim(sources):
        return [{"id": "C01", "anchor": "D1.P02.S1", "text": "A's phones exploded",
                 "type": "allegation", "status": "unsupported", "refs": [], "sources": sources}]

    weak = synth(r, ledger=claim([src("https://forum.example.net/t/1", "lead")]), debates=dispute)
    rl = weak["jurisdictions"]["tw"]["red_lines"][key]
    assert rl["status"] == "needs_ruling" and rl["evidence"] == []
    assert rl["weak_evidence"][0]["claim"] == "C01"
    for sources in ([src("https://law.moj.gov.tw/x", "law_database")],
                    [src("https://news.example.com/a", "independent")],
                    [{"url": "https://x.example/1"}], []):
        syn = synth(r, ledger=claim(sources), debates=dispute)
        rl = syn["jurisdictions"]["tw"]["red_lines"][key]
        assert rl["status"] == "confirmed" and rl["evidence"][0]["claim"] == "C01", sources
