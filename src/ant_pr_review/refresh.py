"""Recompute the synthesis from files on disk, and finalize after a fact-check continue."""
from __future__ import annotations

from .consensus import synthesize
from .factcheck import read_ledger, snapshot
from .jsonio import read_json, write_json
from .report import latest_version, write_report
from .review import load_records
from .workspace import Run


def compute_synthesis(run: Run, models: list[str], thresholds: dict[str, float]) -> dict:
    decision = read_json(run.path("10-decision.json"), default={})
    syn = synthesize(matrix=read_json(run.path("03-matrix.json")),
                     reviews=load_records(run, "04-reviews"),
                     debates=load_records(run, "05-debate"),
                     ledger=read_ledger(run), models=models, thresholds=thresholds,
                     rulings=decision.get("rulings", {}))
    write_json(run.path("06-synthesis.json"), syn)
    return syn


def changelog(prev: dict, ledger: list[dict], syn: dict) -> list[str]:
    out = []
    for c in ledger:
        old = prev.get("statuses", {}).get(c["id"])
        if old is None:
            out.append(f"{c['id']}: new claim -> {c['status']}")
        elif old[0] != c["status"]:
            out.append(f"{c['id']}: {old[0]} -> {c['status']}")
    for j, o in syn["jurisdictions"].items():
        before = prev.get("red_lines", {}).get(j, {})
        for k, st in o["red_lines"].items():
            if before.get(k) and before[k] != st["status"]:
                out.append(f"{j} red line {k}: {before[k]} -> {st['status']}")
        pv = prev.get("verdicts", {}).get(j)
        if pv and pv != o["verdict"]:
            out.append(f"{j} verdict: {pv} -> {o['verdict']}")
    if prev.get("verdict") != syn["consolidated"]["verdict"]:
        out.append(f"overall verdict: {prev.get('verdict')} -> {syn['consolidated']['verdict']}")
    return out


def finalize_factcheck(run: Run, models: list[str], thresholds: dict[str, float],
                       lang: str) -> tuple[str, dict | None]:
    """'unchanged' when the ledger matches the last report, else write the next version."""
    v = latest_version(run)
    ledger = read_ledger(run)
    if v == 0:
        return "no_report", None
    prev = read_json(run.path(f"08-report.v{v}.json"))
    if prev["ledger_snapshot"] == snapshot(ledger):
        return "unchanged", prev
    syn = compute_synthesis(run, models, thresholds)
    meta = write_report(run, syn, lang=lang, changelog=changelog(prev, ledger, syn))
    return "updated", meta


def factcheck_blocked(run: Run) -> str | None:
    """'embargo' while the run's card says embargoed and it was not lifted."""
    intake = read_json(run.path("00-intake.json"))
    if intake.get("card", {}).get("embargo") and not run.state().get("embargo_lifted"):
        return "embargo"
    return None


def factcheck_continue(run: Run, backend, models: list[str], thresholds: dict[str, float],
                       lang: str, io, *, say=None) -> str:
    """`factcheck <run> --continue`: retry, then offer continue-later or finalize."""
    from .factcheck import pick_checker, run_checks
    from .i18n import T
    from .ui import radio
    t = T(lang)
    say = say or io.say
    from .scholarly import verify_identifiers
    verify_identifiers(run, say=say)
    summ = run_checks(run, backend, pick_checker(models, models), lang,
                      blocked=factcheck_blocked(run), say=say)
    if summ["left"]:
        reasons = ", ".join(f"{k} {v}" for k, v in summ["reasons"].items())
        io.say(t("fc.summary", done=summ["done"], total=summ["total"], left=summ["left"],
                 reasons=reasons))
        choice = radio(io, t, t("fc.choice"), [("later", t("fc.later")),
                                               ("finalize", t("fc.finalize"))], default="later")
        if choice == "later":
            io.say(t("fc.resume_hint", run=run.id))
            return "later"
    status, meta = finalize_factcheck(run, models, thresholds, lang)
    if status == "unchanged":
        io.say(t("fc.unchanged", v=meta["version"]))
    elif status == "updated":
        io.say(t("fc.updated", v=meta["version"]))
    else:
        io.say(t("fc.no_report", run=run.id))
    return status
