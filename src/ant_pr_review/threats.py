"""The other side's gray and black tactics, anticipated for defence (D-0007, amended):
astroturfing, intrusion, anonymous letters, false flags and others. Each likely kind
says why it is likely here, the early signs in the content, how to verify, what to do
now, where to report and the law. Never how to run a tactic, never how to avoid
detection, never who is behind an account: attribution is for the police and platforms.
The fixed lists (security, impersonation, staff, letters) are made in code."""
from __future__ import annotations

import re

from . import ethics, prompts
from .i18n import T
from .jsonio import write_json, write_text_atomic
from .schemas import THREAT_FIELDS, THREAT_KINDS, THREATS

DIR = "09-plans"
MAX = 10
FIXED = {"cyber": ("passwords", "mfa", "logins", "logs"),
         "impersonation": ("one_channel", "verified"),
         "staff": ("no_reply", "no_contact", "alt"),
         "letters": ("no_forward", "no_details", "preserve", "counsel")}


ACTION_FIELDS = ("verify", "defend", "report")  # what we do: no persona of our own
# Words for the other side's accounts that the general guard does not know; checked only
# in what we do. Telling defence from use by grammar failed review twice (a defensive
# verb laundered "report back after creating burner accounts"), so any of these words in
# verify, defend or report is a hit unless negated, and the prompt asks for the neutral
# "suspicious accounts". Pattern-limited, like the guard itself: the prompt is the control.
EXTRA_PERSONA = [re.compile(x, re.I) for x in (
    r"側翼", r"侧翼", r"養號", r"养号", r"帶節奏", r"寫手", r"写手", r"反串", r"殭屍帳號",
    r"僵尸账号", r"機器人帳號", r"机器人账号", r"網軍", r"网军", r"水軍", r"水军",
    r"\bpose as\b", r"\bshills?\b", r"\bbot accounts?\b", r"\bthrowaway accounts?\b",
    r"\btroll farms?\b", r"\bfake (?:accounts?|reviews?|profiles?)\b",
    r"\bburner accounts?\b", r"\bsock ?puppets?\b", r"\balt(?:ernate)? accounts?\b")]


def field_hits(k: str, text: str) -> list[dict]:
    """Evasion in every field; in what we do (verify, defend, report) also any persona word,
    unless negated. Naming the other side's tactic belongs in why and signs."""
    from .crisis import _s
    text = _s(text)  # the guard reads the text as it will print (security lens)
    hits = ethics.scan_text(text, ("evasion",))
    if k in ACTION_FIELDS:
        v = ethics._view(text)
        for rx in [*ethics._PE, *EXTRA_PERSONA]:
            for m in rx.finditer(v):
                seg = re.split(r"[,，:：]", v[:m.start()])[-1]  # a comma ends the clause here
                if not ethics._negated(seg, len(seg)):
                    hits.append({"category": "persona",
                                 "excerpt": v[max(0, m.start() - 20):m.end() + 20].strip()})
    return hits


def check(data: dict) -> list[dict]:
    return [h for e in (data or {}).get("tactics") or [] if isinstance(e, dict)
            for k in THREAT_FIELDS for h in field_hits(k, str(e.get(k) or ""))]


def _s(v) -> str:
    from .crisis import _s as clean
    return clean(v)


def _redact(data: dict) -> tuple[dict, bool]:
    """Each field loses only what its own check flagged (the review: one hit must not wipe
    the tactic's name and signs)."""
    out, any_hit = [], False
    for e in (data or {}).get("tactics") or []:
        if not isinstance(e, dict):
            continue
        e = dict(e)
        for k in THREAT_FIELDS:
            hits = field_hits(k, str(e.get(k) or ""))
            if hits:
                any_hit = True
                e[k] = _cut(k, _s(e[k]))
        out.append(e)
    return {"tactics": out}, any_hit


def _cut(k: str, text: str) -> str:
    """Each sentence the field's own check flags is replaced by the guard's marker."""
    out = []
    for s in re.split(r"(?<=[.!?。！？\n])", text):
        hits = field_hits(k, s)
        out.append(ethics.MARK.format(cat=hits[0]["category"]) if hits else s.strip())
    return " ".join(x for x in out if x)


def shape(data) -> tuple[list[dict], list[str]]:
    """Known kinds only, at most ten, a person's contact details removed."""
    from .crisis import _no_contacts, _s
    raw = (data or {}).get("tactics") if isinstance(data, dict) else None
    kept, warn = [], []
    for e in raw if isinstance(raw, list) else []:
        if not isinstance(e, dict):
            continue
        if e.get("kind") not in THREAT_KINDS:
            warn.append(f"threat kind {str(e.get('kind'))[:40]} dropped: not a known kind")
            continue
        if e["kind"] != "other" and any(k["kind"] == e["kind"] for k in kept):
            continue  # one row per kind
        kept.append({"kind": e["kind"], **{k: _s(e.get(k)) for k in THREAT_FIELDS}})
    hits = [0]
    kept = _no_contacts(kept[:MAX], hits)
    if hits[0]:
        warn.append(f"{hits[0]} contact detail(s) removed from the threats table")
    return kept, warn


def render(t: T, kept: list[dict], excluded: list[dict] | None = None) -> list[str]:
    from .crisis import _table
    ev = lambda v: ethics.redact(_s(v), ethics.scan_text(_s(v), ("evasion",)))
    out = [t("threats.note"), ""]
    out += _table([t("threats.col.kind")] + [t(f"threats.col.{k}") for k in THREAT_FIELDS],
                  [[t(f"threats.kind.{e['kind']}")] + [e[k] for k in THREAT_FIELDS]
                   for e in kept] or [[""] * (len(THREAT_FIELDS) + 1)])
    for group, items in FIXED.items():
        out += ["", f"### {t('threats.fixed.' + group)}", ""]
        out += [f"- [ ] {t(f'threats.{group}.{k}')}" for k in items]
    if excluded:
        from .crisis import _no_contacts
        excluded = _no_contacts(excluded, [0])  # watch_for is where an account gets named
        out += ["", f"### {t('plans.x')}", "", t("plans.x.note"), ""]
        out += _table([t("plans.x.tactic"), t("plans.x.why"), t("plans.x.law"),
                       t("plans.x.watch"), t("plans.x.alt")],
                      [[ev(e.get(k)) for k in ("tactic", "why", "law", "watch_for",
                                                "lawful_alternative")] for e in excluded])
    return out


def plan_threats(run, backend, writer, lang, risks, article, intake) -> tuple[dict, list[str]]:
    from .plans import _guarded
    data, rep = _guarded(backend, writer, task="threats", system=prompts.threats_system(lang),
                         prompt=prompts.plan_prompt(risks, article, intake), schema=THREATS,
                         check=check)
    if rep["final"]:
        data, rep["redacted"] = _redact(data)
    kept, warn = shape(data)
    t = T(lang)
    write_json(run.path(f"{DIR}/TH.json"), {"tactics": kept})
    write_text_atomic(run.path(f"{DIR}/TH.md"),
                      "\n".join([f"# {t('threats.title')}", ""] + render(t, kept)) + "\n")
    return rep, warn
