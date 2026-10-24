"""Plans: A smallest safe edit, B lawful alternative (or response options for inbound),
C response kit; re-review by a different model; every plan passes the ethics guard
(D-PR-7): one retry with the guard's feedback, then the offending text is removed and
the removal disclosed in ethics.json and the report."""
from __future__ import annotations

import re
import unicodedata

from . import ethics, prompts, timeline
from .backends.base import Backend, BackendError
from .factcheck import read_ledger
from .i18n import T
from .jsonio import read_json, write_json, write_text_atomic
from .revision import apply_changes, diff_text, paragraphs, render_text
from .review import article_view, load_records
from .roster import vendor
from .schemas import (KIT, OPPONENT, OPPONENT_FIELDS, PLAN_A, PLAN_B, PLAN_B_OPERATION,
                      REREVIEW, RESPONSE_OPTIONS)
from .workspace import Run

DIR = "09-plans"


def risk_view(r: dict) -> dict:
    return {k: r[k] for k in ("id", "anchor", "dimension", "scope", "scenario", "standard",
                              "mitigation", "score")}


def pick_writer_checker(models: list[str], active: list[str]) -> tuple[str, str]:
    pool = active or list(models)
    writer = pool[0]
    others = [m for m in pool if m != writer]
    other_vendor = [m for m in others if vendor(m) != vendor(writer)]
    return writer, (other_vendor or others or [writer])[0]


def sentences_of(run: Run) -> dict[str, str]:
    return {s["id"]: s["text"] for p in paragraphs(run).values() for s in p["sentences"]}


def _guarded(backend: Backend, model: str, *, task: str, system: str, prompt: str,
             schema: dict, check) -> tuple[dict, dict]:
    """Call, check, retry once with feedback. Returns (data, report) where report has the
    first and final hits; the caller redacts what is left."""
    res = backend.run(model, task=task, system=system, prompt=prompt, schema=schema)
    data = res.data if not res.refused else None
    rep = {"model": model, "refused": bool(res.refused), "first": [], "retried": False,
           "final": [], "redacted": False}
    if data is None:
        return {}, rep
    hits = check(data)
    rep["first"] = hits
    if hits:
        rep["retried"] = True
        res2 = backend.run(model, task=task, system=system,
                           prompt=prompt + ethics.feedback(hits), schema=schema)
        if res2.data and not res2.refused:
            data = res2.data
        hits = check(data)
    rep["final"] = hits
    return data, rep


def _strings(data) -> list[str]:
    if isinstance(data, str):
        return [data]
    if isinstance(data, dict):
        return [s for v in data.values() for s in _strings(v)]
    if isinstance(data, list):
        return [s for v in data for s in _strings(v)]
    return []


def _scan_all(data: dict) -> list[dict]:
    return [h for s in _strings(data) for h in ethics.scan_text(s)]


def _redact_all(data, hits):
    if isinstance(data, str):
        return ethics.redact(data, hits) if hits else data
    if isinstance(data, dict):
        return {k: _redact_all(v, hits) for k, v in data.items()}
    if isinstance(data, list):
        return [_redact_all(v, hits) for v in data]
    return data


_ENDS = "。！？.!?；;\n"


def has_sentence(text: str, sentence: str) -> bool:
    """The sentence stands on its own in text: at the start or after a sentence end, and
    not inside quotes or another sentence (whitespace-insensitive)."""
    norm = ethics._norm
    body, s = norm(text), norm(sentence)
    if not s:
        return False
    start = body.find(s)
    while start != -1:
        before_ok = start == 0 or body[start - 1] in _ENDS
        end = start + len(s)
        after_ok = end == len(body) or s[-1] in _ENDS or body[end] in _ENDS
        if before_ok and after_ok:
            return True
        start = body.find(s, start + 1)
    return False


_PROTECTED = re.compile(r"[$€£¥]?\d[\d,.]*\s?(?:%|％|萬|万|億|亿|元|million|billion|bn|m)?"
                        r"|「[^」]{1,80}」|“[^”]{1,80}”|\"[^\"]{1,80}\"")


def protected_changes(old: str, new: str) -> tuple[list[str], list[str]]:
    """Numbers, amounts, dates and quotes removed from or added to a paragraph (borrowed:
    docs/REFERENCES.md #13). Removing one may be the fix; adding one is never a guess."""
    norm = lambda m: m.strip().rstrip(".,")
    a = [norm(m) for m in _PROTECTED.findall(old)]
    b = [norm(m) for m in _PROTECTED.findall(new)]
    return [x for x in a if x and x not in b], [x for x in b if x and x not in a]


def keep_locked(paras: dict, replaced: dict[str, str], locked: list[str]) -> tuple[dict, list[str]]:
    """D-0002: a paragraph change that loses a sentence the user locked, or wraps it in
    other words, is dropped; an inserted paragraph right after one is flagged."""
    out, warn = dict(replaced), []
    warn += [f"locked sentence not found in the text, so nothing protects it: {s[:60]}"
             for s in locked if not any(has_sentence(p.get("text", ""), s)
                                        for p in paras.values())]
    for pid, new in replaced.items():
        if pid.endswith("+"):
            near = [s for s in locked if has_sentence(paras.get(pid[:-1], {}).get("text", ""), s)]
            if near:
                warn.append(f"{pid}: inserted paragraph right after a locked sentence; check "
                            f"it does not contradict it: {near[0][:60]}")
            continue
        old = paras.get(pid, {}).get("text", "")
        lost = [s for s in locked if has_sentence(old, s) and not has_sentence(new, s)]
        if lost:
            del out[pid]
            warn.append(f"{pid}: change dropped, it rewrote a locked sentence: {lost[0][:60]}")
    return out, warn


def _without(text: str, sentences: list[str]) -> str:
    """The text with the user's locked sentences taken out: the guard judges what the
    model wrote, not the sentences the user wrote and locked."""
    for s in sentences:
        text = text.replace(s, " ")
    return text


def plan_a(run, backend, writer, lang, risks, article, intake, paras, ledger, sents):
    locked = intake.get("card", {}).get("locked", [])

    def changes(d):
        rep, warn = apply_changes(paras, d.get("paragraphs", []))
        rep, warn2 = keep_locked(paras, rep, locked)
        return rep, warn + warn2

    def check(d):
        rep_, _ = changes(d)
        text = render_text(paras, rep_)
        return [h for v in rep_.values() for h in ethics.scan_text(_without(v, locked))] \
            + _scan_all({k: v for k, v in d.items() if k != "paragraphs"}) \
            + ethics.laundering(text, ledger, sents)

    data, rep = _guarded(backend, writer, task="plan_a", system=prompts.plan_a_system(lang),
                         prompt=prompts.plan_prompt(risks, article, intake), schema=PLAN_A,
                         check=check)
    replaced, warn = changes(data)
    for pid, new in replaced.items():
        removed, added = protected_changes(paras.get(pid, {}).get("text", ""), new)
        if removed or added:
            warn.append(f"{pid}: protected details changed — removed: {', '.join(removed) or '—'};"
                        f" added: {', '.join(added) or '—'}")
    if rep["final"]:
        # Persona and evasion hits are in what the model wrote: redact its paragraphs only,
        # then drop any change whose redaction took a locked sentence with it.
        ev = [h for h in rep["final"] if h["category"] != "laundering"]
        if ev:
            replaced = {pid: ethics.redact(v, ev) for pid, v in replaced.items()}
            replaced, w = keep_locked(paras, replaced, locked)
            warn += [x for x in w if "not found" not in x]
        rep["redacted"] = True
    text = render_text(paras, replaced)
    lau = [h for h in rep["final"] if h["category"] == "laundering"]
    if lau:
        text = ethics.redact(text, lau)
        warn += [f"locked sentence removed as an unsupported allegation: {s[:60]}"
                 for s in locked if any(h["sentence"] == s for h in lau)]
    write_text_atomic(run.path(f"{DIR}/A.md"), text)
    write_text_atomic(run.path(f"{DIR}/A.diff"), diff_text(paras, replaced))
    write_json(run.path(f"{DIR}/corrections.json"), data.get("corrections", []))
    return text, rep, warn


def render_b(t: T, direction: str, data: dict, paras, ledger, sents) -> tuple[str, list[str]]:
    warn: list[str] = []
    if direction == "operation":
        body = (f"# {t('plans.b')}\n\n**{t('plans.recommendation')}:** "
                f"{t('plans.rec.' + data.get('recommendation', 'do_not_proceed'))}\n\n"
                f"{data.get('alternative_plan', '')}\n\n{data.get('rationale', '')}\n")
    elif direction == "inbound":
        rows = "\n".join(f"| {o['option']} | {o['when']} | {o['risks']} | "
                         f"{', '.join(o['addresses'])} |" for o in data.get("options", []))
        body = (f"# {t('plans.b_inbound')}\n\n| {t('plans.option')} | {t('plans.when')} | "
                f"{t('plans.risks')} | {t('plans.addresses')} |\n|---|---|---|---|\n{rows}\n\n"
                f"**{t('plans.recommendation')}:** {data.get('recommended', '')}\n\n"
                f"{data.get('statement_draft', '')}\n")
    elif data.get("recommendation") == "do_not_publish":
        body = (f"# {t('plans.b')}\n\n**{t('plans.recommendation')}:** "
                f"{t('plans.rec.do_not_publish')}\n\n{data.get('alternative', '')}\n\n"
                f"{data.get('notes', '')}\n")
    else:
        replaced, warn = apply_changes(paras, data.get("paragraphs", []))
        heads = "\n".join(f"- {h}" for h in data.get("headline_options", []))
        body = (f"<!-- {t('plans.rec.publish_revised')} -->\n"
                + (f"<!-- {t('plans.headlines')}:\n{heads}\n-->\n" if heads else "")
                + render_text(paras, replaced))
    return body, warn


def plan_b(run, backend, writer, lang, direction, risks, article, intake, paras, ledger, sents):
    t = T(lang)
    schema = {"operation": PLAN_B_OPERATION, "inbound": RESPONSE_OPTIONS}.get(direction, PLAN_B)

    def check(d):
        text, _ = render_b(t, direction, d, paras, ledger, sents)
        return _scan_all(d) + ethics.laundering(text, ledger, sents)

    data, rep = _guarded(backend, writer, task="plan_b",
                         system=prompts.plan_b_system(lang, direction),
                         prompt=prompts.plan_prompt(risks, article, intake), schema=schema,
                         check=check)
    text, warn = render_b(t, direction, data, paras, ledger, sents) if data else ("", [])
    if rep["final"]:
        text = ethics.redact(text, rep["final"])
        rep["redacted"] = True
    write_text_atomic(run.path(f"{DIR}/B.md"), text)
    write_json(run.path(f"{DIR}/B.json"), data)
    return text, rep, warn


_HANDLE = re.compile(r"@|(?:^|[\s/])u/|t\.me/|://|www\.|/user/|\b(?:ID|id)\s*[:：]", re.I)


def kit_keywords(d: dict) -> tuple[list[dict], list[str]]:
    """Typed monitoring terms. A term that looks like an account handle or a link is
    dropped, and the warning does not repeat it (D-PR-10: we never track people)."""
    from .schemas import KEYWORD_KINDS
    kept, dropped = [], 0
    raw = d.get("monitoring_keywords") or []
    for k in raw if isinstance(raw, list) else []:
        if isinstance(k, str):
            k = {"term": k}
        if not isinstance(k, dict):
            continue
        term = unicodedata.normalize("NFKC", str(k.get("term") or "")).strip()
        if not term:
            continue
        if _HANDLE.search(term):
            dropped += 1
            continue
        plats = k.get("platforms") or []
        plats = [plats] if isinstance(plats, str) else [str(p) for p in plats if p]
        kind = k.get("kind") if k.get("kind") in KEYWORD_KINDS else "brand"
        kept.append({"term": term, "kind": kind, "platforms": plats})
    warn = [f"{dropped} monitoring keyword(s) dropped: they looked like account handles or "
            "links"] if dropped else []
    return kept, warn


def render_kit(t: T, d: dict) -> str:
    from .report import cell
    qa = "\n".join(f"- **{q['question']}**\n  {q['answer']}" for q in d.get("qa", []))
    kws, _ = kit_keywords(d)
    by_kind: dict[str, list[str]] = {}
    for k in kws:
        by_kind.setdefault(k["kind"], []).append(
            cell(k["term"]) + (f" ({', '.join(cell(p) for p in k['platforms'])})"
                               if k["platforms"] else ""))
    esc = "\n".join(f"| {e['trigger']} | {e['action']} | {e['owner']} |"
                    for e in d.get("escalation", []))
    formal = (f"## {t('plans.formal')}\n\n{d['formal_statement']}\n\n"
              if str(d.get("formal_statement") or "").strip() else
              f"## {t('plans.formal')}\n\n{t('plans.formal_withheld')}\n\n"
              if d.get("formal_withheld") else "")
    return (f"# {t('plans.c')}\n\n## {t('plans.holding')}\n\n{d.get('holding_statement', '')}\n\n"
            f"{formal}## Q&A\n\n{qa}\n\n## {t('plans.monitor')}\n\n"
            + "\n".join(f"- {t('kw.' + kind)}: {', '.join(v)}" for kind, v in by_kind.items())
            + f"\n\n## {t('plans.escalation')}\n\n| trigger | action | owner |\n|---|---|---|\n{esc}"
            + f"\n\n## {t('plans.do_not_say')}\n\n"
            + "\n".join(f"- {x}" for x in d.get("do_not_say", [])) + "\n")


def kit_shape(data: dict, characterised: bool) -> dict:
    """S-plans-038: a formal statement only when the facts characterise the event."""
    if not characterised:
        data["formal_statement"] = ""
        data["formal_withheld"] = True
    return data


def plan_c(run, backend, writer, lang, risks, article, intake):
    from .grading import characterised_of
    t = T(lang)
    known = characterised_of(intake)
    data, rep = _guarded(backend, writer, task="kit",
                         system=prompts.kit_system(lang, characterised=known),
                         prompt=prompts.plan_prompt(risks, article, intake), schema=KIT,
                         check=_scan_all)
    if rep["final"]:
        data = _redact_all(data, rep["final"])
        rep["redacted"] = True
    if data:
        data = kit_shape(data, known)
    text = render_kit(t, data) if data else ""
    write_text_atomic(run.path(f"{DIR}/C-kit.md"), text)
    rep["keyword_warnings"] = kit_keywords(data)[1] if data else []
    return text, rep


_TAG = re.compile(r"[#＃@＠][^\s#＃@＠]")
OPPONENT_MAX = 8


def opponent_shape(data) -> tuple[list[dict], list[str]]:
    """S-plans-041: the other side's case stays a short third-person summary. A field over
    300 characters, a hashtag or an @handle reads as their copy: that claim is dropped."""
    raw = (data or {}).get("claims") if isinstance(data, dict) else None
    kept, warn = [], []
    for n, c in enumerate(raw if isinstance(raw, list) else [], 1):
        if not isinstance(c, dict):
            continue
        c = {k: str(c.get(k) or "").strip() for k in OPPONENT_FIELDS}
        if any(len(v) > 300 for v in c.values()):
            warn.append(f"opponent claim {n} dropped: a field is over 300 characters")
        elif any(_TAG.search(v) for v in c.values()):
            warn.append(f"opponent claim {n} dropped: it carries a hashtag or a handle")
        elif c["claim"]:
            kept.append(c)
    return kept[:OPPONENT_MAX], warn


def render_opponent(t: T, claims: list[dict]) -> str:
    from .report import cell
    head = "| # | " + " | ".join(t(f"plans.o.{k}") for k in OPPONENT_FIELDS) + " |"
    rows = [f"| {n} | " + " | ".join(cell(c[k]) or "—" for k in OPPONENT_FIELDS) + " |"
            for n, c in enumerate(claims, 1)]
    body = "\n".join([head, "|---:|" + "---|" * len(OPPONENT_FIELDS), *rows]) if claims \
        else t("plans.o.none")
    return f"# {t('plans.o')}\n\n{t('plans.o.note')}\n\n{body}\n"


def plan_o(run, backend, writer, lang, risks, article, intake):
    data, rep = _guarded(backend, writer, task="opponent", system=prompts.opponent_system(lang),
                         prompt=prompts.plan_prompt(risks, article, intake), schema=OPPONENT,
                         check=_scan_all)
    data = _redact_all(data, rep["final"]) if rep["final"] else data
    rep["redacted"] = bool(rep["final"])
    claims, warn = opponent_shape(data)
    write_json(run.path(f"{DIR}/O.json"), {"claims": claims})
    write_text_atomic(run.path(f"{DIR}/O.md"), render_opponent(T(lang), claims))
    return rep, warn


def run_plans(run: Run, backend: Backend, models: list[str], lang: str, *, say=print) -> dict:
    syn = read_json(run.path("06-synthesis.json"))
    intake = read_json(run.path("00-intake.json"))
    direction = intake["direction"]
    reviews = load_records(run, "04-reviews")
    active = [m for m in models if any(r["model"] == m and r.get("status") == "ok"
                                       for r in reviews.values())]
    writer, checker = pick_writer_checker(models, active)
    paras, ledger, sents = paragraphs(run), read_ledger(run), sentences_of(run)
    article = article_view(run)
    risks = [risk_view(r) for r in syn["risks"]]
    out = {"writer": writer, "checker": checker, "warnings": [], "ethics": {}, "plans": []}
    if direction == "outbound":
        say(f"  … A ({writer})")
        a_text, rep, warn = plan_a(run, backend, writer, lang, risks, article, intake, paras,
                                   ledger, sents)
        out["ethics"]["A"], out["warnings"] = rep, out["warnings"] + warn
        out["plans"].append("A")
    say(f"  … B ({writer})")
    b_text, rep, warn = plan_b(run, backend, writer, lang, direction, risks, article, intake,
                               paras, ledger, sents)
    out["ethics"]["B"], out["warnings"] = rep, out["warnings"] + warn
    out["plans"].append("B")
    say(f"  … C ({writer})")
    c_text, rep = plan_c(run, backend, writer, lang, risks, article, intake)
    out["warnings"] += rep.pop("keyword_warnings", [])
    out["ethics"]["C"] = rep
    say(f"  … O ({writer})")
    rep, warn = plan_o(run, backend, writer, lang, risks, article, intake)
    out["ethics"]["O"], out["warnings"] = rep, out["warnings"] + warn
    say(f"  … T ({writer})")
    unverified = [c["id"] for c in ledger
                  if c.get("status") in ("unsupported", "cannot_verify", "pending")]
    tl, rep, tl_stages = timeline.plan_t(backend, writer, checker, lang, risks, article, intake,
                                         _guarded, unverified)
    out["ethics"]["T"] = rep
    write_json(run.path(f"{DIR}/T.json"), tl)
    write_text_atomic(run.path(f"{DIR}/T.md"), timeline.render(T(lang), tl))
    rr = {"checker": checker}
    stages = []
    texts = {"A": a_text if "A" in out["plans"] else None, "B": b_text, "C": c_text}
    for name, text in texts.items():
        if text is None:
            continue
        st = {"stage": name, "writer": writer, "reviewer": checker, "status": "skipped",
              "reason": "no_risks" if not risks else "empty", "result": ""}
        if risks and text.strip():
            say(f"  … re-review {name} ({checker})")
            try:
                res = backend.run(checker, task="rereview", system=prompts.rereview_system(lang),
                                  prompt=prompts.rereview_prompt(risks, text), schema=REREVIEW)
            except BackendError as e:
                st.update(status="failed", reason=e.reason)
            else:
                if res.refused:
                    st.update(status="refused", reason="refused")
                else:
                    rr[name] = (res.data or {"verdicts": []})["verdicts"]
                    counts: dict[str, int] = {}
                    for v in rr[name]:
                        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
                    st.update(status="ok", reason="",
                              result=", ".join(f"{k} {n}" for k, n in counts.items()))
        stages.append(st)
    out["stages"] = stages + tl_stages
    write_json(run.path(f"{DIR}/rereview.json"), rr)
    write_json(run.path(f"{DIR}/ethics.json"), out["ethics"])
    write_json(run.path(f"{DIR}/summary.json"), out)
    return out
