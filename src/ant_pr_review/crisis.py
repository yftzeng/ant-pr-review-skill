"""Crisis mode (D-0007): from the event alone, with no question asked, a printable response
sheet for the first hours. The fixed parts (the team, the first 30 minutes, the legal
checklist, the business-head questions, press-conference preparation, the update log and
the sign-off) are made in code; a model fills the fact sheet, the response kit, the
timeline and the other side's case. Markdown first; PDF and DOCX beside it."""
from __future__ import annotations

import re
from datetime import datetime

from . import export, plans, prompts, timeline
from .backends.base import Backend
from .catalog import ACTIVATION, GRADES, OWNERS, SIGNALS
from .i18n import T
from .jsonio import read_json, write_json, write_text_atomic
from .review import article_view
from .schemas import AUDIENCES, CRISIS_FACTS, HOLDING_FIELDS, CHANNEL_FIELDS
from .timeline import rel as timeline_rel
from .workspace import Run

BLANK = plans.BLANK
DIR = "09-plans"  # the kit, timeline and other side's case land where plans put them
SECTIONS = ("bluf", "objective", "team", "first30", "facts", "damage", "holding", "qa",
            "do_not_say", "timeline", "notify", "legal", "questions", "opponent", "threats",
            "press",
            "log", "signoff", "next")
TEAM = ("lead", "spokesperson", "legal", "pr", "frontline", "operations", "it")
FIRST30 = ("team", "gag", "pause", "evidence", "safety", "log")
LEGAL = ("report", "privacy", "contracts", "insurance", "hold", "disclosure")
QUESTIONS = ("sign", "knew", "check", "worst", "other_side")
PRESS = ("speaker", "rehearse", "length", "answer", "record", "never")
PRIORITY = ("affected", "staff", "regulators", "partners", "exchange", "investors", "press",
            "public")
_HANDLE = re.compile(r"[@＠]|://|www\.|t\.me/|(?:^|\s)u/", re.I)
# A person's contact details: an email, a phone number, an @handle or a profile link
# (security lens, tier 3). Names cannot be told apart by pattern: the prompt forbids them.
CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"
                     r"|(?<![\w-])(?:\+\d{1,3}[\s-]?\(?\d{1,4}\)?|\(?0\d{1,3}\)?)"
                     r"(?:[\s-]?\d{3,4}){2}(?![\w-])"
                     r"|[@＠][\w.]{2,}|(?:https?://|www\.)\S+|t\.me/\S+|(?<!\w)u/\w+")
REMOVED = "〔×〕"


def _s(v) -> str:
    return " ".join(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(v or "")).split())


def _no_contacts(v, hits: list[int]):
    if isinstance(v, str):
        new, n = CONTACT.subn(REMOVED, v)
        hits[0] += n
        return new
    if isinstance(v, dict):
        return {k: _no_contacts(x, hits) for k, x in v.items()}
    if isinstance(v, list):
        return [_no_contacts(x, hits) for x in v]
    return v


def _md(v) -> str:
    """Model text as inert markdown: cell() escapes links, images, HTML, tables and boxes;
    a leading list marker is escaped too, so it never becomes a bullet or a ticked box."""
    from .report import cell
    s = cell(v)
    return re.sub(r"^([-+*]|\d+[.)])(?=\s)", lambda m: "\\" + m.group(1), s) or BLANK


def facts_shape(raw) -> tuple[dict, list[str]]:
    """S-crisis-005: a rumour is false only with counter-evidence; an owner or due not given
    is a blank; an outlet that looks like a person's handle is dropped; only known signals
    count, and the grade they suggest is the model's, for the user to confirm."""
    d = raw if isinstance(raw, dict) else {}
    warn: list[str] = []
    rumours = []
    for r in d.get("rumours") or []:
        if not isinstance(r, dict) or not _s(r.get("claim")):
            continue
        v = r.get("verdict") if r.get("verdict") in ("true", "partly", "false") else "unverified"
        ce = _s(r.get("counter_evidence"))
        if v == "false" and not ce:
            v = "unverified"
        rumours.append({"claim": _s(r["claim"]), "verdict": v, "counter_evidence": ce})
    pending = [{"question": _s(p.get("question")), "owner_role": _s(p.get("owner_role")) or BLANK,
                "due": _s(p.get("due")) or BLANK}
               for p in d.get("pending") or [] if isinstance(p, dict) and _s(p.get("question"))]
    media = []
    for m in d.get("media") or []:
        if not isinstance(m, dict) or not _s(m.get("outlet")):
            continue
        if _HANDLE.search(_s(m["outlet"])):
            warn.append("a media entry was dropped: it looked like a person's handle or a link")
            continue
        media.append({"outlet": _s(m["outlet"]), "deadline": _s(m.get("deadline")) or BLANK})
    signals = [x for x in dict.fromkeys(x for x in d.get("suggested_signals") or []
                                        if isinstance(x, str)) if x in SIGNALS]
    graded = [SIGNALS[x] for x in signals]
    grade = min(graded, key=GRADES.index) if graded else None
    stake = [s for s in d.get("stakeholders") or [] if isinstance(s, dict)
             and s.get("group") in AUDIENCES]
    stake.sort(key=lambda s: PRIORITY.index(s["group"]) if s["group"] in PRIORITY else 99)
    out = {"summary": _s(d.get("summary")), "objective": _s(d.get("objective")),
           "suggested_signals": signals, "grade": grade,
           "w5h1": {k: _s((d.get("w5h1") or {}).get(k)) for k in
                    ("who", "what", "when", "where", "why", "how")},
           "times": {k: _s((d.get("times") or {}).get(k)) for k in
                     ("occurred_at", "known_at", "exposed_at")},
           "verified": [{"fact": _s(v.get("fact")), "evidence": _s(v.get("evidence")) or BLANK}
                        for v in d.get("verified") or [] if isinstance(v, dict)
                        and _s(v.get("fact"))],
           "pending": pending, "rumours": rumours,
           "impact": {k: _s((d.get("impact") or {}).get(k)) for k in
                      ("people", "money", "batch_risk", "operations")},
           "minors": bool(d.get("minors")),
           "stakeholders": [{"group": s["group"], "need": _s(s.get("need")),
                             "channel": _s(s.get("channel"))} for s in stake],
           "media": media, "actions_done": [_s(x) for x in d.get("actions_done") or [] if _s(x)]}
    hits = [0]
    out = {k: (v if k in ("suggested_signals", "grade") else _no_contacts(v, hits))
           for k, v in out.items()}
    if hits[0]:
        warn.append(f"{hits[0]} contact detail(s) removed from the fact sheet: an email, phone "
                    "number, handle or link of a person")
    return out, warn


def _cell(v) -> str:
    from .report import cell
    return cell(v) or BLANK


def _table(head: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + \
        ["| " + " | ".join(_cell(c) if c != "" else " " for c in r) + " |" for r in rows]


def _demote(md: str) -> list[str]:
    """An embedded plan file: its title dropped, its headings two levels down."""
    lines = (md or "").splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return ["##" + ln if ln.startswith("#") else ln for ln in lines]


def _timeline(t: T, tl: dict) -> list[str]:
    """The timeline in six columns, narrow enough for A4."""
    if not isinstance(tl, dict) or not (tl.get("steps") or tl.get("dropped")):
        return [BLANK]
    gray = f" — {t('crisis.needs_approval')} □"  # S-crisis-008: never without it
    steps = _no_contacts([{k: s.get(k) for k in ("action", "notes", "trigger", "stop")}
                          for s in tl["steps"]], [0])  # every printed step field
    tl = dict(tl, steps=[dict(s, **c) for s, c in zip(tl["steps"], steps)])
    rows = [[timeline_rel(s["day"]), s.get("time") or "",
             s["action"] + (gray + (f" ({s['notes']})" if s.get("notes") else "")
                            if s.get("category") == "gray" else ""),
             t("crisis.audience." + s["audience"]) if s.get("audience") in AUDIENCES else "",
             " / ".join(x for x in (s.get("trigger"), s.get("stop")) if x),
             "; ".join(s.get("warnings") or [])] for s in tl["steps"]]
    out = _table([t("plans.t.rel"), t("plans.t.when"), t("plans.t.action"),
                  t("crisis.col.group"), t("plans.t.trigger"), "⚠"], rows) if rows else [BLANK]
    if tl.get("dropped"):
        out += ["", f"### {t('plans.t.dropped')}", ""]
        out += [f"- {_md(_no_contacts(x['action'], [0]))}: "
                f"{t('plans.t.reason.' + x['reason'])}" for x in tl["dropped"]]
    return out


def render(t: T, d: dict, *, kit: dict | str, timeline: dict, opponent: str, intake: dict,
           version: str = "v1", when: str = "", threats: list | None = None) -> str:
    card = intake.get("card") or {}
    h = lambda k: ["", f"## {t('crisis.h.' + k)}", ""]
    L = [f"# {t('crisis.title')}", "",
         f"{t('export.confidential')} · {t('export.version')} {version}"
         + (f" · {t('export.time')} {when}" if when else "")]
    g = d.get("grade")
    L += h("bluf") + [_md(d["summary"]), "",
                      f"- {t('crisis.grade')}: {t('grade.' + g) if g else t('grade.none')} "
                      f"({t('crisis.grade_unconfirmed')})"]
    if g:
        L += [f"- {t('crisis.owner')}: {t('owner.' + OWNERS[g])}",
              f"- {t('crisis.activation')}: {t('activation.' + ACTIVATION[g])}"]
    L += [f"- [ ] {t('signal.' + s)}" for s in d["suggested_signals"]]
    L += h("objective") + [_md(d["objective"])]
    L += h("team") + _table([t("crisis.col.role"), t("crisis.col.unit"), t("crisis.col.contact"),
                             t("crisis.col.ready")],
                            [[t("crisis.team." + r), "", "", "□"] for r in TEAM])
    L += h("first30") + [f"- [ ] {t('plans.t.pause_promo') if k == 'pause' else t('crisis.first30.' + k)}"
                         for k in FIRST30]
    L += h("facts") + [f"### 5W1H", ""] + _table(
        [t("crisis.col.item"), t("crisis.col.content")],
        [[k.upper() if len(k) > 1 else k, d["w5h1"][k]] for k in d["w5h1"]])
    times = {k: d["times"].get(k) or card.get(k) or "" for k in d["times"]}
    L += ["", f"### {t('crisis.times')}", ""] + _table(
        [t("crisis.col.item"), t("crisis.col.when")],
        [[t(f"card.{k}.label"), times[k]] for k in times])
    L += ["", f"### {t('crisis.verified')}", ""] + _table(
        [t("crisis.col.fact"), t("crisis.col.evidence")],
        [[v["fact"], v["evidence"]] for v in d["verified"]] or [["", ""]])
    L += ["", f"### {t('crisis.pending')}", ""] + _table(
        [t("crisis.col.question"), t("crisis.col.owner"), t("crisis.col.due"), "□"],
        [[p["question"], p["owner_role"], p["due"], "□"] for p in d["pending"]] or [["", "", "", "□"]])
    L += ["", f"### {t('crisis.rumours')}", ""] + _table(
        [t("crisis.col.claim"), t("crisis.col.verdict"), t("crisis.col.counter")],
        [[r["claim"], t("crisis.verdict." + r["verdict"]), r["counter_evidence"]]
         for r in d["rumours"]] or [["", "", ""]])
    if d["actions_done"]:
        L += ["", f"### {t('crisis.actions_done')}", ""] + [f"- {_md(a)}" for a in d["actions_done"]]
    L += h("damage") + _table([t("crisis.col.item"), t("crisis.col.content")],
                              [[t("crisis.impact." + k), v] for k, v in d["impact"].items()])
    L += ["", f"- {t('crisis.minors')}: "
          + (f"{t('crisis.minors_yes')} ({t('signal.minors')})" if d["minors"] else t("ui.no"))]
    L += h("holding") + _holding(t, kit)
    L += h("qa") + _qa(t, kit)
    dns = kit.get("do_not_say") if isinstance(kit, dict) else []
    L += h("do_not_say") + ([f"- {_md(x)}" for x in dns or []] or [BLANK])
    L += h("timeline") + _timeline(t, timeline)
    L += h("notify") + _table(
        [t("crisis.col.group"), t("crisis.col.need"), t("crisis.col.channel"), "□"],
        [[t("crisis.audience." + s["group"]), s["need"], s["channel"], "□"]
         for s in d["stakeholders"]] or [["", "", "", "□"]])
    L += ["", f"### {t('crisis.media')}", ""] + _table(
        [t("crisis.col.outlet"), t("crisis.col.deadline")],
        [[m["outlet"], m["deadline"]] for m in d["media"]] or [["", ""]])
    jur = "、".join(t("jur." + j) for j in card.get("jurisdictions") or []) or "—"
    L += h("legal") + [f"{t('crisis.counsel')} ({jur})", ""] + \
        [f"- [ ] {t('crisis.legal.' + k)}" for k in LEGAL]
    L += h("questions") + [f"- [ ] {t('crisis.q.' + k)}" for k in QUESTIONS]
    L += h("opponent") + (_demote(opponent) or [BLANK])
    from .threats import render as render_threats
    L += h("threats") + render_threats(t, threats or [], (timeline or {}).get("excluded")
                                       if isinstance(timeline, dict) else None)
    L += h("press") + [f"- [ ] {t('crisis.press.' + k)}" for k in PRESS]
    L += h("log") + _table([t("export.version"), t("export.time"), t("crisis.col.change"),
                            t("crisis.col.approved")],
                           [[version, when, t("crisis.log.first" if version == "v1" else "crisis.log.rerun"), ""]] + [["", "", "", ""]] * 4)
    L += h("signoff") + _table([t("export.signoff.role"), t("export.signoff.sign"),
                                t("export.signoff.date")], [["", "", ""]] * 3)
    L += h("next") + [f"- {t('crisis.next.drafting')}", f"- {t('crisis.next.audit')}",
                      "", f"> {t('crisis.disclaimer')}"]
    return "\n".join(L) + "\n"


def _holding(t: T, kit) -> list[str]:
    if not isinstance(kit, dict) or not kit:
        return [BLANK]
    hold = kit.get("holding")
    out = [f"- **{t('crisis.holding.' + k)}**: {_md((hold or {}).get(k))}"
           for k in HOLDING_FIELDS] if isinstance(hold, dict) else \
        [_md(kit.get("holding_statement"))]
    ch = kit.get("channels") if isinstance(kit.get("channels"), dict) else {}
    for k in CHANNEL_FIELDS:
        if _s(ch.get(k)):
            out += ["", f"### {t('plans.channel.' + k)}", "", _md(ch[k])]
    return out


def _qa(t: T, kit) -> list[str]:
    if not isinstance(kit, dict):
        return [BLANK]
    out = []
    for key, title in (("qa", "Q&A"), ("frontline_qa", t("plans.frontline_qa"))):
        items = [q for q in kit.get(key) or [] if isinstance(q, dict)]
        if items:
            out += ["", f"### {title}", ""]
            out += [f"- **{_md(q.get('question'))}** {_md(q.get('answer'))}" for q in items]
    return out or [BLANK]


def _refusals(task: str, rep: dict) -> list[str]:
    """A refusal or a redaction is said on screen, never a silent blank in the sheet."""
    out = [f"{task}: the model refused; its part of the sheet is blank"] \
        if rep.get("refused") else []
    if rep.get("final"):
        out.append(f"{task}: text the ethics guard flagged was removed")
    return out


def run_crisis(run: Run, backend: Backend, models: list[str], lang: str, *, say=print) -> dict:
    t = T(lang)
    intake = read_json(run.path("00-intake.json"))
    if intake.get("purpose") != "crisis":
        return {"status": "not_applicable"}
    writer = models[0]
    article = article_view(run)
    say(f"  … {t('crisis.facts_call')} ({writer})")
    data, rep = plans._guarded(backend, writer, task="crisis_facts",
                               system=prompts.crisis_system(lang),
                               prompt=prompts.crisis_prompt(article, intake), schema=CRISIS_FACTS,
                               check=plans._scan_all)
    if rep["final"]:
        data = plans._redact_all(data, rep["final"])
    facts, warnings = facts_shape(data)
    warnings += _refusals("crisis_facts", rep)
    write_json(run.path("crisis.json"), facts)
    say(f"  … C ({writer})")
    _, krep = plans.plan_c(run, backend, writer, lang, [], article, intake)
    warnings += krep.pop("keyword_warnings", []) + _refusals("kit", krep)
    kit = read_json(run.path(f"{DIR}/C-kit.json"), default={})
    say(f"  … O ({writer})")
    orep, owarn = plans.plan_o(run, backend, writer, lang, [], article, intake)
    warnings += owarn + _refusals("opponent", orep)
    say(f"  … TH ({writer})")
    from .threats import plan_threats
    threp, thwarn = plan_threats(run, backend, writer, lang, [], article, intake)
    warnings += thwarn + _refusals("threats", threp)
    say(f"  … T ({writer})")
    tl, trep, stages = timeline.plan_t(backend, writer, writer, lang, [], article, intake,
                                       plans._guarded, [], grade=facts["grade"])
    warnings += _refusals("timeline", trep) + [
        t("plans.stage.not_reviewed", stage=s["stage"], reason=s["reason"] or s["status"])
        for s in stages if s["status"] not in ("ok", "skipped")]
    version = f"v{read_json(run.path(f'{DIR}/crisis-summary.json'), default={}).get('n', 0) + 1}"
    tl_md = timeline.render(t, tl)
    write_json(run.path(f"{DIR}/T.json"), tl)
    write_text_atomic(run.path(f"{DIR}/T.md"), tl_md)
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = render(t, facts, kit=kit, timeline=tl,
                threats=read_json(run.path(f"{DIR}/TH.json"), default={}).get("tactics", []),
                opponent=run.path(f"{DIR}/O.md").read_text(encoding="utf-8"),
                intake=intake, version=version, when=when)
    write_text_atomic(run.path("crisis.md"), md)
    res = export.export_md(run.path("crisis.md"), lang, version=version, when=when)
    out = {"status": "done", "writer": writer, "warnings": warnings, "n": int(version[1:]),
           "notes": export.notes(t, res)}
    write_json(run.path(f"{DIR}/crisis-summary.json"), out)
    return out

