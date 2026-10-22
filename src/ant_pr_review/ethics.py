"""Ethics guard for plans (D-PR-7): plans may only move toward lawful, disclosed and
provable communication. Pattern-based (en/zh); a paraphrase can slip past it, so the
prompts carry the same rule (known limit).

Categories:
- evasion: advice to hide who is behind a message or to dodge detection/attribution
- persona: fake identities, sockpuppets, comments posing as independent people
- laundering: an unsupported or unverifiable allegation kept verbatim
"""
from __future__ import annotations

import re
import unicodedata

# A negation counts only when it governs the match: at most 3 words before it, in the
# same clause. Broad words ("no", "without", "avoid") are left out on purpose: "no one
# will know these are fake accounts" and "avoid detection by using alt accounts" are
# hits, not advice against the practice.
_NEG_WORD = (r"(?:\b(?:not|never|don'?t|do not|must not|should not|avoid using|stop using|"
             r"refrain from|against|instead of|prohibit(?:ed)?|ban(?:ned)?)\b|不要|切勿|勿|"
             r"禁止|嚴禁|严禁|不得|不應|不应|不可|避免使用|停止|不使用|拒絕|拒绝|而非|取代|別|别|"
             r"從未|从未|並未|并未|未曾|絕不|绝不)")
_NEG = re.compile(_NEG_WORD + r"(?:\W*\w+){0,3}\W*$", re.I)
_NOT_NEG = re.compile(r"(?:don'?t|do not|never) (?:hesitate|forget)|not only|不要猶豫|不要犹豫|"
                      r"別忘|别忘|不要忘|不只|不僅|不仅", re.I)
_CLAUSE_END = re.compile(r"[.!?。！？;；\n]")

EVASION = [
    r"avoid (?:being |getting )?(?:traced|tracked|detected|identified|attributed|linked)",
    r"(?:can'?t|cannot|won'?t|will not) be (?:traced|linked|attributed) (?:back )?to",
    r"untraceable", r"hide (?:that )?(?:we|our|the company|the brand)",
    r"without (?:revealing|disclosing) (?:that )?(?:we|our|it is us)",
    r"(?:rotate|different|separate|change) (?:the )?ip(?: address)?s?\b", r"\bvpn\b.{0,30}hide",
    r"(?:strip|remove|scrub) (?:the )?metadata",
    r"(?:avoid|evade|dodge|bypass|get around) (?:the )?(?:platform |the platform'?s? )?"
    r"(?:detection|moderation|bans?|filters?)",
    r"避免被(?:追查|追溯|發現|发现|查到|識破|识破|抓到|溯源)", r"不會被(?:發現|发现|查到|追溯)",
    r"(?:不|无法|無法)被(?:追查|追溯|溯源)", r"隱藏(?:我方|公司|品牌|真實)身分",
    r"隐藏(?:我方|公司|品牌|真实)身份", r"(?:換|换|分散|輪換|轮换)\s?ip",
    r"(?:刪除|删除|清除)(?:檔案)?(?:metadata|中繼資料|元数据|元資料)", r"規避(?:平台|偵測|審查)",
    r"规避(?:平台|检测|审核)",
    # AI-detection evasion (docs/REFERENCES.md #12): making machine text pass as human
    r"humani[sz]e (?:the |this |our )?(?:text|copy|content|post|draft|ai)",
    r"(?:bypass(?:es)?|evade[sd]?|beats?|fools?|pass(?:es)?|gets? past|avoids?) (?:the |an? )?"
    r"ai[- ]?(?:content )?detect",
    r"undetectable(?: by)? (?:ai|detectors?|gptzero)",
    r"降(?:低)?\s?ai\s?(?:率|感|味)", r"去\s?ai\s?(?:味|感|化)",
    r"(?:绕过|繞過|规避|規避|躲过|躲過)\s?ai\s?(?:检测|檢測|偵測|侦测)",
]

PERSONA = [
    r"sock ?puppets?", r"fake (?:accounts?|profiles?|personas?|reviews?)", r"burner accounts?",
    r"alt(?:ernate)? accounts?", r"posing as (?:a |an )?(?:customer|user|fan|netizen|employee)",
    r"pretend(?:ing)? to be (?:a |an )?(?:customer|user|fan|independent)",
    r"as if (?:written|posted) by (?:a |an )?(?:customer|user|independent)",
    r"人頭帳號", r"人头账号", r"分身帳號", r"假帳號", r"假账号", r"小帳", r"小号", r"馬甲", r"马甲",
    r"水軍", r"水军", r"網軍", r"网军", r"假扮", r"冒充", r"偽裝成(?:網友|消費者|顧客|路人)",
    r"伪装成(?:网友|消费者|顾客|路人)", r"以(?:網友|网友|消費者|消费者|路人)(?:身分|身份|口吻)",
    r"帶風向", r"带节奏", r"带风向",
    # an independent voice for our content (docs/REFERENCES.md #12)
    r"sound(?:s|ing)? like (?:an? )?(?:ordinary|real|regular|independent|genuine|normal) "
    r"(?:user|customer|person|netizen|consumer|fan)",
    r"像(?:普通|真實|真实|一般)(?:網友|网友|用戶|用户|消費者|消费者|路人)",
    # coordinated posts passed off as spontaneous (D-0005)
    r"(?:so (?:that )?(?:it|they|this|these|the posts?) |make (?:it|them|this|these|the posts?) )"
    r"(?:looks?|appears?|seems?|look|appear|seem) (?:organic|grassroots|spontaneous)",
    r"看起來(?:像是?)?自發", r"看起来(?:像是?)?自发",
]

_EV = [re.compile(p, re.I) for p in EVASION]
_PE = [re.compile(p, re.I) for p in PERSONA]


def _view(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _negated(text: str, start: int) -> bool:
    seg = _CLAUSE_END.split(text[max(0, start - 60):start])[-1]
    return bool(_NEG.search(_NOT_NEG.sub(" ", seg)))


def scan_text(text: str, categories: tuple[str, ...] = ("evasion", "persona")) -> list[dict]:
    """Hits in one text: [{category, excerpt}]. A negated mention ('never use sockpuppets',
    '不要使用人頭帳號') is advice against the practice and is not a hit."""
    v = _view(text)
    hits = []
    for cat, rxs in (("evasion", _EV), ("persona", _PE)):
        if cat not in categories:
            continue
        for rx in rxs:
            for m in rx.finditer(v):
                if _negated(v, m.start()):
                    continue
                hits.append({"category": cat,
                             "excerpt": v[max(0, m.start() - 20):m.end() + 20].strip()})
    return hits


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", _view(s))


def laundering(text: str, ledger: list[dict], sentences: dict[str, str]) -> list[dict]:
    """Allegations the ledger could not support whose sentence is still in the text
    verbatim. sentences: sentence id -> original text."""
    body = _norm(text)
    hits = []
    for c in ledger:
        if c.get("type") != "allegation" or c.get("status") not in ("unsupported", "cannot_verify"):
            continue
        sent = sentences.get(c["anchor"])
        if sent and len(_norm(sent)) >= 6 and _norm(sent) in body:
            hits.append({"category": "laundering", "claim": c["id"], "anchor": c["anchor"],
                         "excerpt": sent[:120], "sentence": sent})
    return hits


def feedback(hits: list[dict]) -> str:
    lines = [f"- {h['category']}: {h['excerpt']}" for h in hits]
    return ("\n\nYour previous answer was rejected by the ethics guard for:\n" + "\n".join(lines)
            + "\nRewrite without any of these: no concealment, no personas, and remove (do not "
              "reword) allegations that could not be supported.")


MARK = "[removed by ethics guard: {cat}]"


def redact(text: str, hits: list[dict]) -> str:
    """Remove each hit's whole sentence from text and leave a visible marker."""
    out = text
    for h in hits:
        if h["category"] == "laundering":
            out = out.replace(h["sentence"], MARK.format(cat=f"laundering {h['claim']}"))
            continue
        for sent in re.split(r"(?<=[.!?。！？\n])", out):
            if any(rx.search(_view(sent)) for rx in (_EV if h["category"] == "evasion" else _PE)) \
                    and scan_text(sent):
                out = out.replace(sent, MARK.format(cat=h["category"]) + " ")
    return out
