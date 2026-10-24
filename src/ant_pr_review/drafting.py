"""Drafting mode (D-0005): a fixed brief, two versions that differ in approach, each
audited by the same matrix, ranked in code; the recommended one becomes the run's source
so the full review, plans and report follow on it."""
from __future__ import annotations

import json
import re
import shutil
import tomllib
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from . import prompts
from .backends.base import Backend, BackendError
from .consensus import VERDICT_ORDER
from .i18n import T
from .intake import posture_of
from .jsonio import read_json, sha256_bytes, write_json, write_text_atomic
from .plans import _guarded, _redact_all, _scan_all, pick_writer_checker
from .reaudit import audit_text
from .schemas import DRAFT, DRAFT_REASON, DRAFT_REVIEW
from .ui import ask_text, radio
from .workspace import Run

DIR = "08-drafts"
KINDS = ["incident", "product", "data", "conduct", "dispute", "rumour", "announcement",
         "other"]
EMOTIONS = ["anger", "fear", "grief", "confusion", "betrayal", "disappointment", "worry",
            "none"]
DECISIONS = ["publish", "revise", "delay", "respond", "monitor", "investigate", "withdraw",
             "escalate"]
TIER4 = ["injury", "data_breach", "lawsuit", "regulator", "criminal", "minors"]
FACT_STATUS = {"confirmed": "C", "alleged": "A", "unknown": "U"}
ACTION_STATUS = {"actions_done": "done", "actions_in_progress": "in_progress",
                 "actions_planned": "planned"}
CLASSES = ["public", "internal", "not_supportable", "needs_validation"]
PARTS = ["stance", "facts", "cause", "measures", "other"]
FOUR_PARTS = ["stance", "facts", "cause", "measures"]
MAX_QUESTIONS = 3
DRAFT_REVIEW_KINDS = ["unsupported_fact", "contradiction", "missing_part", "status_overstated",
                      "early_conclusion", "commitment_crossed", "tone", "other"]
ALIKE = 0.8


# ---- the brief ----------------------------------------------------------------

def _texts(v) -> list[str]:
    v = [v] if isinstance(v, str) else (v if isinstance(v, list) else [])
    return [" ".join(str(x).split()) for x in v if str(x).strip()]


def _one_of(raw: dict, key: str, allowed: list[str], default: str | None = None) -> str:
    v = raw.get(key) or default
    if v not in allowed:
        raise ValueError(f"brief {key} {v!r}: choose from {allowed}")
    return v


def check_brief(raw: dict) -> dict:
    """Validate a brief (from the questions or a file) and number its facts C1.., A1.., U1.."""
    if not isinstance(raw, dict):
        raise ValueError("the brief must be a table of fields")
    facts = []
    for status, prefix in FACT_STATUS.items():
        facts += [{"id": f"{prefix}{i}", "status": status, "text": x}
                  for i, x in enumerate(_texts(raw.get(status)), 1)]
    if not any(f["status"] in ("confirmed", "alleged") for f in facts):
        raise ValueError("the brief needs at least one confirmed or alleged fact")
    tier4 = _texts(raw.get("tier4"))
    bad = [x for x in tier4 if x not in TIER4]
    if bad:
        raise ValueError(f"brief tier4 {bad}: choose from {TIER4}")
    characterised = raw.get("characterised", raw.get("characterized", False))
    if not isinstance(characterised, bool):
        raise ValueError(f"brief characterised {characterised!r}: choose true or false")
    return {"kind": _one_of(raw, "kind", KINDS), "facts": facts,
            "affected": " ".join(str(raw.get("affected", "")).split()),
            "emotion": _one_of(raw, "emotion", EMOTIONS, "none"),
            "outcome": " ".join(str(raw.get("outcome", "")).split()),
            "decision": _one_of(raw, "decision", DECISIONS, "publish"),
            "prior": _texts(raw.get("prior")),
            "actions": [{"text": x, "status": s} for k, s in ACTION_STATUS.items()
                        for x in _texts(raw.get(k))],
            "approvers": _texts(raw.get("approvers")),
            "characterised": characterised,
            "cannot_commit": check_bounds(_texts(raw.get("cannot_commit"))),
            "tier4": list(dict.fromkeys(tier4))}


def _bnorm(s: str) -> str:
    """For cannot-commit matching: width, case, spacing, punctuation and format characters
    dropped. Simplified and traditional forms stay different: list both."""
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", s or "")).casefold()


def short_bound(line: str) -> bool:
    b = _bnorm(line)
    return len(b) < (2 if _CJK.search(b) else 3)


def check_bounds(lines: list[str]) -> list[str]:
    """Trailing punctuation dropped; a line too short to match only itself is refused."""
    out = [re.sub(r"[\s\W_]+$", "", x) for x in lines]
    bad = [x for x in out if short_bound(x)]
    if bad:
        raise ValueError(f"brief cannot_commit {bad}: too short to match safely; "
                         "give a key phrase of two CJK characters or three letters or more")
    return list(dict.fromkeys(out))


def load_brief(path) -> dict:
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    return tomllib.loads(raw) if p.suffix.lower() == ".toml" else json.loads(raw)


# ---- checks in code -------------------------------------------------------------

# A gap marker in any bracket, a bare marker, or a run of blanks (models drift from the
# prompted token). An ordinary bracket such as a footnote "[1]" is not a gap.
_GAP_WORD = (r"待查證|待查证|待確認|待确认|待補|待补|to verify|tbd|tbc|placeholder|insert\b|fill in"
             r"|請填|请填")
PLACEHOLDER = re.compile(r"[\[【〔<{（(][^\]】〕>}）)\n]{0,40}?(?:" + _GAP_WORD + r")[^\]】〕>}）)\n]{0,40}?[\]】〕>}）)]"
                         r"|待查證|待查证|to verify|○○|□□|_{3,}|\bXXX?\b(?!L)", re.I)
INTERNAL = re.compile(r"\[removed by ethics guard|\b(?:TODO|TBD|FIXME)\b|內部備註|内部备注|僅供內部|仅供内部|[【（(\[]\s*(?:內部|内部|internal|INTERNAL)"
                      r"|INTERNAL ONLY|internal only", re.I)


def deliverable_issues(text: str) -> list[dict]:
    """Placeholders and internal notes left in a text meant for publication."""
    out = []
    for n, line in enumerate((text or "").splitlines(), 1):
        for kind, rx in (("placeholder", PLACEHOLDER), ("internal", INTERNAL)):
            out += [{"kind": kind, "match": m.group(0), "line": n} for m in rx.finditer(line)]
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or "")).casefold()


def register(claims: list[dict], brief: dict, text: str) -> tuple[list[dict], list[str]]:
    """N-drafting-001: a claim is public only on a confirmed fact; a not-supportable or
    internal-only claim that the text still contains disqualifies the version."""
    confirmed = {f["id"] for f in brief["facts"] if f["status"] == "confirmed"}
    body, out, why = _norm(text), [], []
    for c in claims:
        if not isinstance(c, dict) or not str(c.get("text", "")).strip():
            continue
        cls = c.get("class") if c.get("class") in CLASSES else "needs_validation"
        basis = [b for b in (c.get("basis") or []) if isinstance(b, str)]
        item = {"text": str(c["text"])[:300], "basis": basis, "class": cls,
                "in_text": _norm(str(c["text"])) in body}
        if cls == "public" and not (basis and set(basis) <= confirmed):
            item.update({"class": "needs_validation", "downgraded": True})
        if item["in_text"] and cls in ("not_supportable", "internal"):
            why.append(f"{cls}: {item['text'][:80]}")
        out.append(item)
    return out, why


def bound_hits(v: dict, bounds: list[str]) -> list[str]:
    """The lines we cannot commit to that the text contains; a negation still counts,
    so the user reads the sentence (S-drafting-019)."""
    body = _bnorm(version_text(v) if isinstance(v, dict) else v)
    return [b for b in bounds if _bnorm(b) and _bnorm(b) in body]


def version_text(v: dict) -> str:
    paras = [p["text"].strip() for p in v.get("paragraphs", []) if p.get("text", "").strip()]
    return (f"# {v['title'].strip()}\n\n" if v.get("title", "").strip() else "") \
        + "\n\n".join(paras) + "\n"


def alike(a: dict, b: dict) -> bool:
    if _norm(a.get("approach", "")) == _norm(b.get("approach", "")):
        return True
    body = lambda v: "\n".join(p.get("text", "") for p in v.get("paragraphs", []))
    return SequenceMatcher(None, body(a), body(b), autojunk=False).ratio() >= ALIKE


_CJK = re.compile(r"[㐀-鿿]")
_SENT = re.compile(r"[^。！？!?]+[。！？!?]?|[^.]+\.?")
OFFICIALESE = re.compile(r"依法處理|依法处理|造成不便|敬請見諒|敬请见谅|深表遺憾|深表遗憾|高度重視|高度重视"
                         r"|any inconvenience|we take (?:this|these|it) (?:very )?seriously"
                         r"|deeply regret|regret any", re.I)
VAGUE_TIME = re.compile(r"盡快|儘快|尽快|儘速|尽速|近期|適當時機|适当时机|as soon as possible|in due course"
                        r"|shortly|at the earliest opportunity", re.I)
NOMINAL = re.compile(r"進行\S{0,8}?(?:動作|作業)|进行\S{0,8}?(?:动作|作业)|做出\S{0,6}?的(?:動作|处理|處理)"
                     r"|相關單位|相关单位|有關單位|有关单位|相關人員|相关人员"
                     r"|\bconduct(?:ed)? an? (?:review|investigation) of\b"
                     r"|\bthe relevant (?:departments|parties|authorities|units)\b", re.I)
INTENSIFIER = re.compile(r"第一時間|第一时间|全面(?:覆核|复核|排查|檢查|检查|調查|调查|檢測|检测|清查)"
                         r"|徹查|彻查|不放過任何|不放过任何|嚴肅處理|严肃处理"
                         r"|\b(?:immediately|thoroughly|leave no stone unturned|full investigation"
                         r"|comprehensive (?:review|investigation|inspection))\b", re.I)
_COUNTED = (r"(?:車輛|车辆|車|车|產品|产品|批次|用戶|用户|門市|门市|單位|单位|客戶|客户|個案|个案|案例"
            r"|消費者|消费者|訂單|订单|商品|台|輛|辆|件|位)")
VAGUE_QTY = re.compile(r"(?:個別|个别|少數|少数|少量|極少數|极少数|部分)" + _COUNTED +
                       r"|\b(?:some|a few|a small number of|a limited number of|isolated)\s+"
                       r"(?:units|vehicles|cars|products|batches|customers|users|stores|cases"
                       r"|orders|items|devices|accounts)\b", re.I)
_DATE = re.compile(r"\d{1,4}\s*(?:年|月|日|號|号|時|时|:\d)|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul"
                   r"|aug|sep|oct|nov|dec)\w*|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*"
                   r"\s+\d{1,2}|\b(?:19|20)\d\d\b", re.I)
SUPERLATIVE = re.compile(r"最好|最佳|最安全|第一品牌|唯一|頂尖|顶尖|業界領先|业界领先|領導品牌|领导品牌|世界級|世界级"
                         r"|\b(?:best|leading|world-class|unparalleled|unmatched|safest|number one)\b"
                         r"|#1", re.I)


def _long_sentence(s: str) -> bool:
    return len(_CJK.findall(s)) > 90 if _CJK.search(s) else len(s.split()) > 35


def _long_para(s: str) -> bool:
    return len(_CJK.findall(s)) > 250 if _CJK.search(s) else len(s.split()) > 120


def w_checks(v: dict, posture: str) -> list[dict]:
    """W1-W10: readability and accountability, never detection evasion."""
    hits = []
    paras = [p for p in v.get("paragraphs", []) if p.get("text", "").strip()]
    for n, p in enumerate(paras, 1):
        where, text = f"P{n}", p["text"]
        sents = [s for s in (re.findall(r"[^。！？!?]+[。！？!?]?", text) if _CJK.search(text)
                             else re.split(r"(?<=[.!?])\s+", text)) if s.strip()]
        if any(_long_sentence(s) for s in sents):
            hits.append({"id": "W1", "where": where, "hit": "sentence"})
        if _long_para(text):
            hits.append({"id": "W2", "where": where, "hit": "paragraph"})
        for wid, rx in (("W4", OFFICIALESE), ("W5", VAGUE_TIME), ("W6", NOMINAL),
                        ("W8", SUPERLATIVE)):
            hits += [{"id": wid, "where": where, "hit": m.group(0)} for m in rx.finditer(text)]
        hits += [{"id": "W9", "where": where, "hit": m.group(0)} for s in sents
                 if not re.search(r"\d", _DATE.sub("", s)) for m in VAGUE_QTY.finditer(s)]
        hits += [{"id": "W10", "where": where, "hit": m.group(0)} for s in sents
                 if not re.search(r"\d", s) for m in INTENSIFIER.finditer(s)]
    if posture in ("clarify_apologize", "rebut"):
        have = {p.get("part") for p in paras}
        missing = [x for x in FOUR_PARTS if x not in have]
        if missing:
            hits.append({"id": "W3", "where": "", "hit": ", ".join(missing)})
    lead = v.get("lead_5w1h") or {}
    gaps = [k for k in ("who", "what", "when", "where", "why", "how")
            if not str(lead.get(k, "")).strip()]
    if gaps:
        hits.append({"id": "W7", "where": "P1", "hit": ", ".join(gaps)})
    return hits


# ---- examples -------------------------------------------------------------------

EXAMPLES = Path(__file__).resolve().parent / "examples.toml"


def examples_for(posture: str, limit: int = 6) -> list[dict]:
    """Patterns and counters of the posture, alternating so both kinds are shown."""
    ex = [e for e in tomllib.loads(EXAMPLES.read_text(encoding="utf-8"))["example"]
          if e.get("posture") == posture]
    pats = [e for e in ex if e["kind"] == "pattern"]
    cons = [e for e in ex if e["kind"] == "counter"]
    out = []
    while (pats or cons) and len(out) < limit:
        for group in (pats, cons):
            if group and len(out) < limit:
                out.append(group.pop(0))
    return out


def examples_block(ex: list[dict]) -> str:
    if not ex:
        return ""
    lines = ["Examples (paraphrased from case notes, unverified; learn the move, never copy the "
             "wording; a counter is what to avoid):"]
    for e in ex:
        lines.append(f"- [{e['kind']}] {e['org']} {e.get('date') or 'undated'}, {e['part']}: "
                     f"{e['lesson']}")
    return "\n".join(lines)


# ---- ranking ------------------------------------------------------------------

def rank(versions: list[dict]) -> list[str]:
    """Disqualified last, then a cannot-commit hit, the verdict, the top score and the
    pass rate (D-0005)."""
    order = sorted(enumerate(versions), key=lambda iv: (
        bool(iv[1]["disqualified"]), bool(iv[1].get("bounds")), VERDICT_ORDER.index(iv[1]["verdict"]), iv[1]["top"],
        -iv[1]["rate"], iv[0]))
    return [v["id"] for _, v in order]


def _pct(v: dict) -> str:
    return f"{int(100 * v['rate'] + 0.5)}%"


def code_reason(t: T, v: dict) -> str:
    return t("draft.reason_code", id=v["id"], verdict=t("verdict." + v["verdict"]),
             top=v["top"], rate=_pct(v))


def _numbers(v: dict) -> dict:
    return {"id": v["id"], "approach": str(v.get("approach", ""))[:80], "verdict": v["verdict"],
            "top_score": v["top"], "pass_rate": _pct(v), "disqualified": v["disqualified"],
            "placeholders": len(v["placeholders"]), "w_checks": len(v["w"])}


def _scores(syn: dict) -> tuple[str, float, float, int, int]:
    seen, passed, applicable = set(), 0, 0
    top = max([r["score"] for r in syn["risks"]], default=0)
    for o in syn["jurisdictions"].values():
        for i in o["items"]:
            top = max(top, i["score"])
            if (i["item"], i["unit"]) in seen:
                continue
            seen.add((i["item"], i["unit"]))
            vs = [x for x in i["by_model"].values() if x != "na"]
            passed, applicable = passed + vs.count("pass"), applicable + len(vs)
    rate = passed / applicable if applicable else 0.0
    return syn["consolidated"]["verdict"], top, rate, passed, applicable


# ---- the phase ---------------------------------------------------------------------

def _materials(run: Run) -> str:
    from .review import article_view
    sub = Run(run.path(f"{DIR}/materials"))
    return article_view(sub) if sub.path("01-sources/segments.json").exists() else ""


def _clean_versions(data: dict) -> list[dict]:
    out = []
    for v in (data or {}).get("versions", [])[:2]:
        paras = [{"text": str(p.get("text", "")), "part": p.get("part") if p.get("part") in PARTS
                  else "other"} for p in v.get("paragraphs", []) if str(p.get("text", "")).strip()]
        if paras:
            out.append(dict(v, paragraphs=paras))
    return out


def _questions(data: dict) -> list[str]:
    """At most three, cleaned of control characters; one the guard flags is never asked."""
    from . import ethics
    out = []
    for q in data.get("blocking_questions") or []:
        q = " ".join(re.sub(r"\x1b\[[0-9;]*[A-Za-z]|[\x00-\x1f\x7f]", " ", str(q)).split())[:300]
        if q and not ethics.scan_text(q):
            out.append(q)
    return out[:MAX_QUESTIONS]


def holding_only(brief: dict) -> bool:
    """Facts not yet enough to characterise the event, or a tier-4 flag (S-drafting-018)."""
    return bool(brief["tier4"]) or not brief.get("characterised", False)


def _write(backend, writer, lang, intake, brief, material, answers, extra=""):
    system = prompts.draft_system(lang, intake, tier4=bool(brief["tier4"]),
                                  holding=holding_only(brief))
    prompt = prompts.draft_prompt(intake, brief, material, answers,
                                  examples_block(examples_for(posture_of(intake)))) + extra
    return _guarded(backend, writer, task="draft", system=system, prompt=prompt, schema=DRAFT,
                    check=_scan_all)


def run_draft(run: Run, backend: Backend, models: list[str], lang: str,
              thresholds: dict[str, float], *, io, interactive: bool, say=print) -> dict:
    t = T(lang)
    intake = read_json(run.path("00-intake.json"))
    if intake.get("purpose") != "drafting":
        return {"status": "not_applicable"}
    brief = intake["brief"]
    posture = posture_of(intake)
    if posture == "expose" and not any(f["status"] == "confirmed" for f in brief["facts"]):
        return _done(run, {"status": "stopped", "reason": t("draft.expose_needs_fact")})
    matrix = read_json(run.path("03-matrix.json"))
    context = read_json(run.path("02-context.json"), default={"status": "skipped"})
    material = _materials(run)
    writer, checker = pick_writer_checker(models, models)
    run.path("10-final.md").unlink(missing_ok=True)  # an earlier export no longer applies
    # the writer's answer depends on these, the examples and the guard's patterns
    from . import ethics
    digest = sha256_bytes(json.dumps([intake, matrix, context, material, writer,
                                      EXAMPLES.read_text(encoding="utf-8"),
                                      ethics.EVASION + ethics.PERSONA,
                                      prompts.draft_system(lang, intake, tier4=bool(brief["tier4"]),
                                                           holding=holding_only(brief)),
                                      prompts.draft_differ_note()], ensure_ascii=False,
                                     sort_keys=True).encode("utf-8"))
    cached = read_json(run.path(f"{DIR}/writer.json"), default={})
    if cached.get("inputs_sha") == digest:
        versions, rep, open_q, warnings = (cached["versions"], cached["ethics"],
                                           cached["open_questions"], cached["warnings"])
        contradictions = cached.get("contradictions", [])
    else:
        for old in run.path(DIR).glob("V*") if run.path(DIR).exists() else []:
            shutil.rmtree(old) if old.is_dir() else old.unlink()
        say(f"  … {t('draft.writing')} ({writer})")
        answers: list[dict] = []
        data, rep = _write(backend, writer, lang, intake, brief, material, answers)
        questions = _questions(data)
        if questions and interactive:
            for q in questions:
                a = ask_text(io, q).strip()
                if a:
                    answers.append({"question": q, "answer": a})
            if answers:
                data, rep = _write(backend, writer, lang, intake, brief, material, answers)
            questions = _questions(data) if answers else []
        versions, warnings = _clean_versions(data), []
        if len(versions) < 2 or alike(versions[0], versions[1]):
            data2, rep2 = _write(backend, writer, lang, intake, brief, material, answers,
                                 prompts.draft_differ_note())
            again = _clean_versions(data2)
            if again:
                data, rep = data2, rep2
            if len(again) == 2 and not alike(again[0], again[1]):
                versions = again
            else:
                versions, warnings = (again or versions)[:1], ["near_duplicate"]
        if not versions:
            raise BackendError("the writer returned no version", reason="invalid_output")
        open_q = questions
        contradictions = [str(c)[:300] for c in data.get("contradictions", [])][:10]
        for i, v in enumerate(versions, 1):
            v["id"] = f"V{i}"
        write_json(run.path(f"{DIR}/writer.json"), {"inputs_sha": digest, "versions": versions,
                                                     "ethics": rep, "open_questions": open_q,
                                                     "warnings": warnings, "answers": answers,
                                                     "contradictions": contradictions})
    # N-drafting-002: whatever was selected or cached is scanned once more, and redacted
    hits = _scan_all({"v": versions, "q": open_q, "c": contradictions})
    if hits:
        versions, open_q, contradictions = (_redact_all(versions, hits),
                                            _redact_all(open_q, hits),
                                            _redact_all(contradictions, hits))
        rep = dict(rep, final=hits, redacted=True)
    for v in versions:
        text = version_text(v)
        write_text_atomic(run.path(f"{DIR}/{v['id']}.md"), text)
        v["claims"], v["disqualified"] = register(v.get("claims", []), brief, text)
        v["placeholders"] = deliverable_issues(text)
        v["w"] = w_checks(v, posture)
        v["bounds"] = bound_hits(v, brief.get("cannot_commit", []))
    stage = _review_stage(backend, writer, checker, lang, brief, versions, say)
    for v in versions:
        say(f"  … {t('draft.auditing', id=v['id'])}")
        syn = audit_text(run, f"{DIR}/{v['id']}", version_text(v), matrix["units"],
                         matrix["depth"], backend,
                         models, lang, thresholds, say=say)
        v["verdict"], v["top"], v["rate"], v["passed"], v["applicable"] = _scores(syn)
        if not v["applicable"]:  # no reviewer answered: never ranked as clean
            v["disqualified"].append(t("draft.not_audited"))
    if all(not v["applicable"] for v in versions):
        raise BackendError("no version could be audited", reason="error")
    order = rank(versions)
    by_id = {v["id"]: v for v in versions}
    best = by_id[order[0]]
    out = {"status": "done", "writer": writer, "checker": checker, "versions": versions,
           "order": order, "warnings": warnings, "open_questions": open_q, "ethics": rep,
           "contradictions": contradictions,
           "tier4": brief["tier4"], "decision": brief["decision"], "stage": stage,
           "holding": holding_only(brief),
           "brief": {s: sum(f["status"] == s for f in brief["facts"]) for s in FACT_STATUS}}
    if best["disqualified"]:
        return _done(run, dict(out, status="stopped", reason=t("draft.all_disqualified")))
    out["recommended"] = best["id"]
    out["reason"], out["reason_by"] = _reason(backend, checker, lang, t, best, versions)
    chosen = best["id"]
    eligible = [v for v in versions if not v["disqualified"]]
    if interactive and len(eligible) > 1:
        chosen = radio(io, t, t("draft.pick"),
                       [(v["id"], f"{v['id']} {v['approach']} ({t('verdict.' + v['verdict'])}, "
                         f"{_pct(v)})" + (f" · ⚠ {t('draft.bounds_short')}" if v["bounds"] else "")
                        + (f" · {t('draft.recommended')}"
                                          if v["id"] == best["id"] else ""))
                        for v in eligible], default=best["id"])
    out["chosen"] = chosen
    _adopt(run, chosen)
    return _done(run, out)


def _review_stage(backend, writer, checker, lang, brief, versions, say) -> dict:
    st = {"stage": "D", "writer": writer, "reviewer": checker, "status": "skipped",
          "reason": "same_model" if checker == writer else "", "issues": {}}
    if checker == writer:
        return st
    say(f"  … {T(lang)('draft.reviewing')} ({checker})")
    try:
        res = backend.run(checker, task="draft_review", system=prompts.draft_review_system(lang),
                          prompt=prompts.draft_review_prompt(brief, versions), schema=DRAFT_REVIEW)
    except BackendError as e:
        return dict(st, status="failed", reason=e.reason)
    if res.refused or not res.data:
        return dict(st, status="refused", reason="refused")
    ids = {v["id"] for v in versions}
    issues = {r["version"]: [i for i in r.get("issues") or [] if isinstance(i, dict)
                             and i.get("kind") in DRAFT_REVIEW_KINDS]
              for r in res.data.get("versions") or [] if isinstance(r, dict)
              and r.get("version") in ids}
    return dict(st, status="ok", issues=issues)


def _reason(backend, checker, lang, t, best, versions) -> tuple[str, str]:
    """The model writes the reason from the numbers; one citing no number is replaced."""
    try:
        res = backend.run(checker, task="draft_reason", system=prompts.draft_reason_system(lang),
                          prompt=prompts.draft_reason_prompt(best["id"],
                                                             [_numbers(v) for v in versions]),
                          schema=DRAFT_REASON)
        reason = "" if res.refused or not res.data else " ".join(
            str(res.data.get("reason", "")).split())[:600]
    except BackendError:
        reason = ""
    if reason and _cites(reason, best, versions):
        return reason, checker
    return code_reason(t, best), "code"


def _cites(reason: str, best: dict, versions: list[dict]) -> bool:
    """The reason names the recommended version, no other one, and one of its own figures."""
    ids = set(re.findall(r"(?<![A-Za-z0-9])V\d+(?!\d)", reason))
    if ids != {best["id"]}:
        return False
    rest = re.sub(r"(?<![A-Za-z0-9])V\d+(?!\d)|\d*W\d+H?", " ", reason, flags=re.I)
    figures = {_pct(best), str(best["top"]), f"{best['passed']}/{best['applicable']}"}
    return any(re.search(rf"(?<![\d.]){re.escape(f)}(?![\d.]?\d)", rest) for f in figures)


def _adopt(run: Run, vid: str) -> None:
    src, dst = run.path(f"{DIR}/{vid}/01-sources"), run.path("01-sources")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _done(run: Run, out: dict) -> dict:
    write_json(run.path(f"{DIR}/summary.json"), out)
    return out


__all__ = ["Run", "run_draft", "check_brief", "load_brief", "register", "w_checks",
           "deliverable_issues", "alike", "rank", "examples_for", "examples_block"]
