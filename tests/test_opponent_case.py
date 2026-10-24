"""The other side's case, anticipated (S-plans-040..042), and the trademark-suit items
(S-checklist-021, docs/REFERENCES.md #25)."""
from pathlib import Path

from ant_pr_review import plans, prompts, timeline
from ant_pr_review.catalog import item_index
from ant_pr_review.i18n import T
from ant_pr_review.jsonio import read_json
from ant_pr_review.plans import run_plans
from ant_pr_review.schemas import OPPONENT, validate
from test_plans import Q, backend, setup
from helpers import M1, M2

t = T("en")
ROOT = Path(__file__).resolve().parents[1]
CLAIM = {"frame": "a giant bullying a family shop", "claim": "they would say the suit is about "
         "silencing a small rival, not about confusion", "appeal": "small-business owners",
         "channel": "short video", "true_part": "the shop is small and has traded for years",
         "our_evidence": "C2: the registration predates the shop", "response":
         "say what we ask for (stop using the mark), the transition offered, no damages"}


# @S-plans-040
def test_plans_anticipate_the_other_side(tmp_path):
    run = setup(tmp_path)
    b = backend({(M1, "opponent"): {"claims": [CLAIM] * 10 + [dict(CLAIM, frame="#tag")]}})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    assert any("opponent claim 11 dropped" in w for w in out["warnings"])
    call = next(c for c in b.calls if c["task"] == "opponent")
    assert call["schema"] is OPPONENT
    d = read_json(run.path("09-plans/O.json"))
    assert len(d["claims"]) == 8 and not validate(d, OPPONENT)
    md = run.path("09-plans/O.md").read_text()
    for k in ("frame", "claim", "appeal", "channel", "true_part", "our_evidence", "response"):
        assert t(f"plans.o.{k}") in md, k
    assert "family shop" in md and t("plans.o.note") in md
    from ant_pr_review.report import _plans_sections
    sec = "\n".join(_plans_sections(t, run, None))
    assert f"## {t('plans.o')}" in sec and t("plans.o.note") in sec
    for lang in ("zh-TW", "zh-CN"):
        assert T(lang)("plans.o") != t("plans.o")
    assert T("zh-TW")("plans.o") == "對方論述預判（模擬）"


# @S-plans-041
def test_other_side_described_never_written():
    s = prompts.opponent_system("en")
    for needle in ("third person", "never their statement", "hashtag", "private person",
                   "we do not hold", "what is true"):
        assert needle in s, needle
    long = dict(CLAIM, claim="x" * 301)
    tag = dict(CLAIM, response="post it with #BoycottThem")
    handle = dict(CLAIM, channel="tag @someone")
    kept, warn = plans.opponent_shape({"claims": [CLAIM, long, tag, handle]})
    assert kept == [CLAIM] and len(warn) == 3
    assert plans.opponent_shape({"claims": [dict(CLAIM, claim="x" * 300)]})[0]
    assert plans.opponent_shape(None) == ([], [])
    md = plans.render_opponent(t, [])
    assert t("plans.o.none") in md


# @S-plans-041 the ethics guard runs on the answer
def test_other_side_guarded(tmp_path):
    run = setup(tmp_path)
    bad = dict(CLAIM, response="use sockpuppet accounts to seed the frame")
    b = backend({(M1, "opponent"): {"claims": [bad]}})
    out = run_plans(run, b, [M1, M2], "en", say=Q)
    assert "sockpuppet" not in run.path("09-plans/O.md").read_text()
    assert out["ethics"]["O"]["final"] and out["ethics"]["O"]["redacted"] is True


# @S-plans-042
def test_excluded_black_names_the_kind_of_case():
    s = prompts.timeline_system("en", ["white", "black"])
    assert "kind of public case" in s and "never how to avoid detection" in s
    assert "court judgment" in s
    assert T("zh-TW")("plans.x.exposure") == "公開被揭穿的案例類型"
    assert t("plans.x.exposure") == "kind of public case that exposed it"
    d = timeline.build([], {}, [{f: "x" for f in timeline.EX_FIELDS}], {}, ["white", "black"],
                       "", ["tw"], "w")
    assert "公開被揭穿的案例類型" in timeline.render(T("zh-TW"), d)


# @S-checklist-021
def test_bully_frame_and_underdog_prop():
    idx = item_index()
    l15 = idx["LEG-15"]["text"]
    for needle in ("larger", "smaller", "actually asked", "proportionate", "settlement", "staff"):
        assert needle in l15, needle
    s12 = idx["SOC-12"]["text"]
    for needle in ("props", "us against them", "the text we answer", "attacking the people"):
        assert needle in s12, needle
    refs = (ROOT / "docs" / "REFERENCES.md").read_text()
    sec = refs.split("## 25.", 1)[1]
    assert "zBdHYTw1SEo" in sec and "nothing is quoted" in sec
    for phrase in ("單點爆破", "文化掠奪者", "商標霸權", "打工人"):
        assert phrase not in sec, phrase
