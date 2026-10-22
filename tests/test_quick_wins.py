from ant_pr_review.backends.base import Result
from ant_pr_review.factcheck import check_claim
from ant_pr_review.report import lint_report
from helpers import ScriptBackend


def finding(fid, **kw):
    f = {"id": fid, "anchor": "D1.P01.S1", "scenario": "scn", "standard": "std",
         "why_it_matters": "why", "mitigation": "mit"}
    f.update(kw)
    return f


def lint(*findings):
    return lint_report({"risks": list(findings), "unverified": []}, "# R\n", [])


# @S-review-matrix-021
def test_tone_lint():
    probs = lint(finding("F01", scenario="This is sloppy work."),
                 finding("F02", why_it_matters="作者根本不懂這個主題"),
                 finding("F03", mitigation="I am the editor and require changes"),
                 finding("F04", mitigation="We recommend rejection of this piece."))
    text = "\n".join(probs)
    for fid in ("F01", "F02", "F03", "F04"):
        assert fid in text, (fid, probs)
    assert lint(finding("F05", scenario="The claim in P02 lacks a source.")) == []


# @S-review-matrix-022
def test_absence_needs_checked_surfaces():
    probs = lint(finding("F01", anchor="absence: whole piece - expected sources"))
    assert any("absence without checked surfaces" in p for p in probs)
    assert lint(finding("F02", anchor="absence: whole piece - expected sources; checked: body, footnotes")) == []


# @S-factcheck-ledger-011
def test_sources_have_accessed_at(tmp_path):
    res = Result(model="", model_id="", data={
        "status": "supported", "reason": "", "sources": [{"url": "https://a.example/x",
                                                          "supporting_excerpt": "e"}]},
        tool_calls=[{"name": "WebSearch", "input": {}}], tool_results=["https://a.example/x"])
    c = check_claim(ScriptBackend({("s", "factcheck"): res}), "s",
                    {"id": "C01", "anchor": "D1.P01", "text": "t", "type": "other",
                     "status": "pending", "reason": "", "sources": [], "refs": []}, "", "en")
    acc = c["sources"][0]["accessed_at"]
    assert acc[:4].isdigit() and "T" in acc
    from ant_pr_review.report import source_urls
    assert acc[:10] in source_urls(c["sources"])
