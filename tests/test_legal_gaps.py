"""Phase 1 of the legal gap review: confidentiality, privilege and competition law."""
from ant_pr_review import drafting
from ant_pr_review.catalog import item_index
from ant_pr_review.i18n import T


# @S-checklist-024
def test_confidentiality_and_competition_items():
    idx = item_index()
    leg16, leg17 = idx["LEG-16"], idx["LEG-17"]
    for needle in ("trade secret", "confidentiality agreement", "settlement", "privilege", "disclosure duty"):
        assert needle in leg16["text"], needle
    for needle in ("prices", "trade association", "disparage", "boycott", "infringement",
                   "warning letters", "competition authority"):
        assert needle in leg17["text"], needle
    assert "whether the competition authority's rules" in leg17["text"]
    for i in (leg16, leg17):
        assert i["lens"] == "legal" and "outbound" in i["directions"]
        assert "counsel" in i["text"] and "postures" not in i


def _v(text):
    return {"paragraphs": [{"text": text, "part": "facts"}], "lead_5w1h": {}}


# @S-drafting-031
def test_legal_advice_is_flagged_and_lawyers_alone_are_not():
    for text in ("依律師建議，我們暫不回應細節。", "根據法律顧問的意見，本公司決定下架。",
                 "依律师建议，我们暂不回应。", "On the advice of counsel, we will not comment.",
                 "Our lawyers advised us to pause the product.", "Our lawyer advised us to suspend sales.",
                 "Our lawyers advised that we should suspend sales.", "律師的建議是暫停銷售。",
                 "律师的建议是暂停销售。", "On the advice of\ncounsel, we suspended sales.",
                 "Our lawyers told us we must suspend sales to comply with the injunction.",
                 "Our counsel told us to pause the campaign.", "律師建議我們立即停止銷售，以免違反禁制令。",
                 "律师建议我们立即停止销售。"):
        for posture in ("clarify_apologize", "promote", "rebut", "expose"):
            hits = [h for h in drafting.w_checks(_v(text), posture) if h["id"] == "W19"]
            assert hits and hits[0]["where"] == "P1", (text, posture)
    for text in ("我們已委任律師處理。", "We have retained counsel.", "律師公會今天發表聲明。",
                 "Our lawyers told us they are available for a meeting tomorrow.",
                 "我們尚未收到律師的建議。", "我们不会公开律师的建议。"):
        assert "W19" not in {h["id"] for h in drafting.w_checks(_v(text), "promote")}, text
    assert "privilege" in T("en")("draft.w.W19")
    assert "律師" in T("zh-TW")("draft.w.W19") and "律师" in T("zh-CN")("draft.w.W19")
