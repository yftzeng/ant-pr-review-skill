"""Plans: A smallest safe edit, B lawful alternative (or response options for inbound),
C response kit; re-review by a different model; every plan passes the ethics guard
(D-PR-7): one retry with the guard's feedback, then the offending text is removed and
the removal disclosed in ethics.json and the report."""
from __future__ import annotations

from . import ethics, prompts
from .backends.base import Backend
from .factcheck import read_ledger
from .i18n import T
from .jsonio import read_json, write_json, write_text_atomic
from .revision import apply_changes, diff_text, paragraphs, render_text
from .review import article_view, load_records
from .roster import vendor
from .schemas import KIT, PLAN_A, PLAN_B, PLAN_B_OPERATION, REREVIEW, RESPONSE_OPTIONS
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


def plan_a(run, backend, writer, lang, risks, article, intake, paras, ledger, sents):
    def check(d):
        rep, _ = apply_changes(paras, d.get("paragraphs", []))
        text = render_text(paras, rep)
        return _scan_all(d) + ethics.laundering(text, ledger, sents)

    data, rep = _guarded(backend, writer, task="plan_a", system=prompts.plan_a_system(lang),
                         prompt=prompts.plan_prompt(risks, article, intake), schema=PLAN_A,
                         check=check)
    replaced, warn = apply_changes(paras, data.get("paragraphs", []))
    text = render_text(paras, replaced)
    if rep["final"]:
        text = ethics.redact(text, rep["final"])
        rep["redacted"] = True
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


def render_kit(t: T, d: dict) -> str:
    qa = "\n".join(f"- **{q['question']}**\n  {q['answer']}" for q in d.get("qa", []))
    esc = "\n".join(f"| {e['trigger']} | {e['action']} | {e['owner']} |"
                    for e in d.get("escalation", []))
    return (f"# {t('plans.c')}\n\n## {t('plans.holding')}\n\n{d.get('holding_statement', '')}\n\n"
            f"## Q&A\n\n{qa}\n\n## {t('plans.monitor')}\n\n"
            + ", ".join(d.get("monitoring_keywords", []))
            + f"\n\n## {t('plans.escalation')}\n\n| trigger | action | owner |\n|---|---|---|\n{esc}"
            + f"\n\n## {t('plans.do_not_say')}\n\n"
            + "\n".join(f"- {x}" for x in d.get("do_not_say", [])) + "\n")


def plan_c(run, backend, writer, lang, risks, article, intake):
    t = T(lang)
    data, rep = _guarded(backend, writer, task="kit", system=prompts.kit_system(lang),
                         prompt=prompts.plan_prompt(risks, article, intake), schema=KIT,
                         check=_scan_all)
    if rep["final"]:
        data = _redact_all(data, rep["final"])
        rep["redacted"] = True
    text = render_kit(t, data) if data else ""
    write_text_atomic(run.path(f"{DIR}/C-kit.md"), text)
    return text, rep


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
    _, rep = plan_c(run, backend, writer, lang, risks, article, intake)
    out["ethics"]["C"] = rep
    rr = {"checker": checker}
    if risks:
        for name in [p for p in ("A", "B") if p in out["plans"]]:
            say(f"  … re-review {name} ({checker})")
            res = backend.run(checker, task="rereview", system=prompts.rereview_system(lang),
                              prompt=prompts.rereview_prompt(
                                  risks, (a_text if name == "A" else b_text)), schema=REREVIEW)
            rr[name] = (res.data or {"verdicts": []})["verdicts"] if not res.refused else []
    write_json(run.path(f"{DIR}/rereview.json"), rr)
    write_json(run.path(f"{DIR}/ethics.json"), out["ethics"])
    write_json(run.path(f"{DIR}/summary.json"), out)
    return out
