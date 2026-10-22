"""The timeline of means (D-0002): the writer schedules white and gray steps; a reviewer
from another vendor labels every step again and the stricter label wins. A black step is
never scheduled: with black ticked it is listed in the excluded table, otherwise it is
dropped and disclosed. The excluded table is scanned for evasion in every field and for
personas in the lawful alternative only (naming the tactic is the point of the table)."""
from __future__ import annotations

import re
from datetime import date, timedelta

from . import ethics, prompts
from .backends.base import Backend, BackendError
from .catalog import MEANS, sensitive_dates_near
from .schemas import ATTENTION_STAGES
from .i18n import T
from .intake import means_of, posture_of
from .schemas import CLASSIFY_MEANS, TIMELINE

STRICT = {m: n for n, m in enumerate(MEANS)}  # white < gray < black
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
STEP_FIELDS = ("action", "channel", "notes", "trigger", "stop")
EARLY = {"press", "public"}  # must not come before the first step for affected parties
EX_FIELDS = ("tactic", "why", "law", "exposure", "watch_for", "lawful_alternative")
MAX_STEPS = 30


def timeline_hits(d: dict) -> list[dict]:
    hits = []
    for s in d.get("steps", []):
        for k in STEP_FIELDS:
            hits += ethics.scan_text(str(s.get(k, "")))
    for e in d.get("excluded", []):
        for k in EX_FIELDS:
            cats = ("evasion", "persona") if k == "lawful_alternative" else ("evasion",)
            hits += ethics.scan_text(str(e.get(k, "")), cats)
    return hits


def redact_timeline(d: dict, hits: list[dict]) -> dict:
    ev = [h for h in hits if h["category"] == "evasion"]
    steps = [{k: (ethics.redact(v, hits) if k in STEP_FIELDS and isinstance(v, str) else v)
              for k, v in s.items()} for s in d.get("steps", [])]
    excluded = [{k: (ethics.redact(v, hits if k == "lawful_alternative" else ev)
                     if isinstance(v, str) else v) for k, v in e.items()}
                for e in d.get("excluded", [])]
    return {"steps": steps, "excluded": excluded}


def _day(v) -> int:
    try:
        return max(-30, min(365, int(v)))
    except (TypeError, ValueError):
        return 0


def _t0(publish_at: str) -> date | None:
    try:
        return date.fromisoformat((publish_at or "").strip()[:10])
    except ValueError:
        return None


CRISIS = {"clarify_apologize", "rebut"}  # postures where someone may be affected


def _order_warnings(kept: list[dict], posture: str, t: T, unverified: list[str]) -> None:
    """Affected parties first, staff no later than the public (D-0003). In a crisis
    posture no promotion before the affected are helped; the exchange or regulator filing
    before the press; no public step while claims are unverified (docs/REFERENCES.md #8-11).
    A tie is not 'after', and a missing time counts as early for the press and late for the
    affected."""
    def key(s, early: bool):
        return (s["day"], s["time"] or ("00:00" if early else "99:99"))
    affected = [key(s, False) for s in kept if s["audience"] == "affected"]
    public = [s for s in kept if s["audience"] in EARLY]
    if affected:
        first = min(affected)
        for s in public:
            if key(s, True) <= first:
                s["warnings"].append(t("plans.t.warn_before_affected"))
    elif public and posture in CRISIS:
        public[0]["warnings"].append(t("plans.t.warn_no_affected"))
    if posture in CRISIS:
        for s in kept:
            if s["promotional"] and (not affected or key(s, True) <= min(affected)):
                s["warnings"].append(t("plans.t.warn_promo_first"))
    filings = [key(s, False) for s in kept if s["audience"] == "exchange"]
    if filings:
        for s in public:
            if key(s, True) <= min(filings):
                s["warnings"].append(t("plans.t.warn_before_filing"))
    if unverified and public:
        first = min(public, key=lambda s: key(s, True))
        first["warnings"].append(t("plans.t.warn_unverified", ids=", ".join(unverified[:8])))
    if public:
        first_public = min(key(s, True) for s in public)
        for s in kept:
            if s["audience"] == "staff" and key(s, False) > first_public:
                s["warnings"].append(t("plans.t.warn_staff_late"))


def _blackouts(code: str) -> list[dict]:
    from .catalog import JURISDICTIONS, pack
    return [b for b in pack(code).get("blackout", []) if b.get("kind") == "poll"] \
        if code in JURISDICTIONS else []


def _clean(text, cats: tuple[str, ...] = ("evasion", "persona")) -> str:
    s = str(text or "")
    return ethics.redact(s, ethics.scan_text(s, cats))


def rel(day: int) -> str:
    return "T0" if day == 0 else f"T{day:+d}d"


def build(steps: list[dict], labels: dict[int, dict] | None, excluded: list[dict],
          flags: dict[int, str], means: list[str], publish_at: str,
          jurisdictions: list[str], withheld: str, unreviewed: str = "not reviewed",
          t: T | None = None, posture: str = "clarify_apologize",
          unverified: list[str] | None = None) -> dict:
    """labels: 1-based step number -> {category, reason}, or None when the review did not
    run (every step is then not_reviewed)."""
    kept, dropped, black = [], [], []
    dropped += [{"action": str(s.get("action", "")), "category": "", "reason": "too_many"}
                for s in steps[MAX_STEPS:]]
    for n, s in enumerate(steps[:MAX_STEPS], 1):
        wcat = s.get("category") if s.get("category") in MEANS else "black"
        lab = (labels or {}).get(n)
        if s.get("guard_hit"):
            dropped.append({"action": s.get("action", ""), "category": "black",
                            "reason": "ethics_guard"})
            continue
        if lab is None:
            dropped.append({"action": s.get("action", ""), "category": wcat,
                            "reason": "not_reviewed"})
            continue
        ccat = lab.get("category") if lab.get("category") in MEANS else "black"
        cat = max(wcat, ccat, key=STRICT.get)
        if cat == "black":
            why = str(lab.get("reason") or s.get("notes", ""))  # reviewer text: untrusted
            black.append({"tactic": s.get("action", ""), "why": _clean(why, ("evasion",)),
                          "law": "", "exposure": "", "watch_for": "", "lawful_alternative": ""})
            continue
        if cat not in means:
            dropped.append({"action": s.get("action", ""), "category": cat,
                            "reason": "outside_means"})
            continue
        kept.append({**{k: str(s.get(k, "")) for k in STEP_FIELDS}, "order": n,
                     "audience": str(s.get("audience", "")), "paid": bool(s.get("paid")),
                     "promotional": bool(s.get("promotional")), "poll": bool(s.get("poll")),
                     "stage": s.get("stage") if s.get("stage") in ATTENTION_STAGES else "",
                     "silence": bool(s.get("silence")),
                     "day": _day(s.get("day")),
                     "time": s.get("time") if TIME_RE.match(str(s.get("time", ""))) else "",
                     "category": cat, "writer_category": wcat, "reviewer_category": ccat,
                     "reviewer_reason": _clean(lab.get("reason", ""))})
    kept.sort(key=lambda s: (s["day"], s["time"] or "99:99", s["order"]))
    first = next((s for s in kept if s["silence"]), None)
    for s in kept:  # one silence point: the first
        s["silence"] = s is first
    t0 = _t0(publish_at)
    if t0:  # a poll inside a jurisdiction's publication blackout is not scheduled
        blocked = []
        for s in kept:
            when = (t0 + timedelta(days=s["day"])).isoformat()
            if s.get("poll") and any(b["start"] <= when <= b["end"]
                                     for j in jurisdictions for b in _blackouts(j)):
                blocked.append(s)
                dropped.append({"action": s["action"], "category": s["category"],
                                "reason": "poll_blackout"})
        kept = [s for s in kept if s not in blocked]
    for n, s in enumerate(kept, 1):
        s["n"] = n
        s["date"] = (t0 + timedelta(days=s["day"])).isoformat() if t0 else ""
        s["warnings"] = [f"{d['date']} {d['note']} ({d['jurisdiction']})"
                         for d in sensitive_dates_near(jurisdictions, s["date"], days=1)] \
            if s["date"] else []
    t = t or T("en")
    _order_warnings(kept, posture, t, unverified or [])
    for s in kept:
        if s["paid"] and not s["stop"].strip():
            s["warnings"].append(t("plans.t.warn_paid_stop"))
        if s["silence"] and s["stage"] in ("pre_problem", "alarmed"):
            s["warnings"].append(t("plans.t.warn_early_silence"))
    ex = []
    if "black" in means:
        for n, e in enumerate(excluded, 1):
            e = {k: str(e.get(k, "")) for k in EX_FIELDS}
            # Unreviewed (labels None) is withheld like a flagged entry (D-0002).
            reason = flags.get(n) if labels is not None else unreviewed
            if reason is not None:
                e["exposure"] = e["watch_for"] = withheld.format(reason=reason)
                e["withheld"] = True
            ex.append(e)
        ex += black
    else:
        dropped += [{"action": b["tactic"], "category": "black", "reason": "black"}
                    for b in black]
    return {"steps": kept, "dropped": dropped, "excluded": ex, "means": means,
            "t0": publish_at or "", "t0_invalid": bool((publish_at or "").strip()) and t0 is None,
            "local_to": (jurisdictions or [""])[0]}


def _c(v) -> str:
    from .report import safe
    return safe(v)


def _ev(v) -> str:
    """Excluded-table cell: a tactic may be named (persona words allowed), evasion never."""
    from .report import cell
    s = str(v or "")
    return cell(ethics.redact(s, ethics.scan_text(s, ("evasion",))))


def render(t: T, d: dict) -> str:
    L = [f"# {t('plans.t')}", "", t("plans.t.note", jur=t("jur." + d["local_to"])
                                    if d["local_to"] else "—",
                                    t0=_c(d["t0"]) or "T0"), ""]
    if d.get("t0_invalid"):
        L += [f"> ⚠ {t('plans.t.t0_invalid', t0=_c(d['t0']))}", ""]
    L += [f"## {t('plans.t.table')}", "",
          f"| # | {t('plans.t.rel')} | {t('plans.t.when')} | {t('plans.t.action')} | "
          f"{t('plans.t.category')} | {t('plans.t.channel')} | {t('plans.t.notes')} | "
          f"{t('plans.t.trigger')} | {t('plans.t.stage')} | ⚠ |",
          "|---:|---|---|---|---|---|---|---|---|---|"]
    for s in d["steps"]:
        when = " ".join(x for x in (s["date"], s["time"]) if x) or "—"
        cat = t("means." + s["category"] + ".short")
        if s["category"] != s["writer_category"]:
            cat += f" ({t('plans.t.relabelled')})"
        trig = " / ".join(x for x in (s["trigger"], s["stop"]) if x)
        stage = t("stage." + s["stage"]) if s.get("stage") else ""
        if s.get("silence"):
            stage = (stage + " · " if stage else "") + f"**{t('plans.t.silence')}**"
        L.append(f"| {s['n']} | {rel(s['day'])} | {when} | {_c(s['action'])} | {cat} | "
                 f"{_c(s['channel'])} | {_c(s['notes'])} | {_c(trig)} | {stage} | "
                 f"{_c('; '.join(s['warnings']))} |")
    if not d["steps"]:
        L.append(f"| — | | | {t('report.none')} | | | | | | |")
    if d["dropped"]:
        L += ["", f"## {t('plans.t.dropped')}", ""]
        L += [f"- {_c(x['action'])}"
              + (f" ({t('means.' + x['category'] + '.short')})" if x["category"] else "")
              + f": {t('plans.t.reason.' + x['reason'])}" for x in d["dropped"]]
    if "black" in d["means"]:
        L += ["", f"## {t('plans.x')}", "", t("plans.x.note"), "",
              f"| {t('plans.x.tactic')} | {t('plans.x.why')} | {t('plans.x.law')} | "
              f"{t('plans.x.exposure')} | {t('plans.x.watch')} | {t('plans.x.alt')} |",
              "|---|---|---|---|---|---|"]
        for e in d["excluded"]:
            cells = [_c(e[k]) if k == "lawful_alternative" else _ev(e[k]) for k in EX_FIELDS]
            L.append(" | ".join(["", *cells, ""]).strip())
        if not d["excluded"]:
            L.append(f"| {t('report.none')} | | | | | |")
    return "\n".join(L) + "\n"


def plan_t(backend: Backend, writer: str, checker: str, lang: str, risks: list[dict],
           article: str, intake: dict, guarded,
           unverified: list[str] | None = None) -> tuple[dict, dict, list[dict]]:
    """Returns (timeline, ethics report, stage reviews)."""
    t = T(lang)
    means = means_of(intake)
    data, rep = guarded(backend, writer, task="timeline",
                        system=prompts.timeline_system(lang, means),
                        prompt=prompts.timeline_prompt(risks, article, intake), schema=TIMELINE,
                        check=timeline_hits)
    flagged = {n for n, s in enumerate(data.get("steps", []), 1)
               if any(ethics.scan_text(str(s.get(k, ""))) for k in STEP_FIELDS)}
    if rep["final"]:
        data = redact_timeline(data, rep["final"])
        rep["redacted"] = True
    # A step the guard still flags after the retry is never scheduled, blanked or not.
    steps = [dict(s, guard_hit=n in flagged) for n, s in enumerate(data.get("steps", []), 1)]
    excluded = list(data.get("excluded", []))
    if "black" not in means:
        excluded = []
    labels, flags = None, {}
    review = {"writer": writer, "reviewer": checker, "status": "skipped", "reason": "empty",
              "result": ""}
    if steps or excluded:
        try:
            res = backend.run(checker, task="classify_means", system=prompts.classify_system(lang),
                              prompt=prompts.classify_prompt(steps, excluded),
                              schema=CLASSIFY_MEANS)
            if res.refused or not res.data:
                review.update(status="refused", reason="refused")
            else:
                labels = {}
                for lab in res.data.get("labels", []):  # two labels for one step: the stricter
                    n = lab.get("step")
                    if not isinstance(n, int):
                        continue
                    cat = lab.get("category") if lab.get("category") in MEANS else "black"
                    if n not in labels or STRICT[cat] > STRICT[labels[n]["category"]]:
                        labels[n] = dict(lab, category=cat)
                flags = {f["entry"]: f.get("problem", "") for f in
                         res.data.get("excluded_flags", []) if isinstance(f.get("entry"), int)}
                review.update(status="ok", reason="")
                # Numbers outside 1..N (a 0-based answer, say) would shift labels onto the
                # neighbouring steps: the whole review is void.
                if any(not 1 <= n <= len(steps) for n in labels) or \
                        any(not 1 <= n <= len(excluded) for n in flags):
                    labels, flags = None, {}
                    review.update(status="invalid", reason="step numbers out of range")
        except BackendError as e:
            review.update(status="failed", reason=e.reason)
    card = intake.get("card", {})
    out = build(steps, labels, excluded, flags, means, card.get("publish_at", ""),
                card.get("jurisdictions", []), t("plans.x.withheld"),
                t("plans.x.unreviewed"), t, posture_of(intake), unverified)
    stricter = sum(1 for s in out["steps"] if s["category"] != s["writer_category"])
    black = sum(1 for n in range(1, len(steps) + 1)
                if (labels or {}).get(n, {}).get("category") == "black")
    stages = [dict(review, stage="T", result=t("plans.stage.t_result", stricter=stricter,
                                                 black=black,
                                                 dropped=len(out["dropped"])))]
    if "black" in means:
        stages.append(dict(review, stage="X", result=t("plans.stage.x_result",
                                                         withheld=sum(1 for e in out["excluded"]
                                                                      if e.get("withheld")))))
    return out, rep, stages
