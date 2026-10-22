"""Decision gate: red-line rulings per jurisdiction, plan choice (or hold), Style Guide."""
from __future__ import annotations

import re
import shutil
from datetime import datetime

from .i18n import T
from .jsonio import append_jsonl, read_json, read_jsonl, write_json, write_text_atomic
from .store import Store
from .ui import IO, confirm, radio
from .workspace import Run

STYLE_CATEGORIES = {"term", "banned_word", "name"}


def pending_rulings(syn: dict) -> list[str]:
    """'<jurisdiction>:<red line>' for every red line that waits for a human."""
    return [f"{j}:{k}" for j, o in syn["jurisdictions"].items()
            for k, v in o["red_lines"].items() if v["status"] == "needs_ruling"]


def ask_rulings(io: IO, t: T, syn: dict, keys: list[str]) -> dict[str, str]:
    rulings = {}
    for jk in keys:
        j, k = jk.split(":", 1)
        v = syn["jurisdictions"][j]["red_lines"][k]
        io.say(f"{t('jur.' + j)} · {t('redline.' + k)} — {', '.join(v['supporters'])}")
        for c in v["comments"]:
            io.say(f"  {c['model']}: {c['comment']}")
        for d in v["dissent"]:
            io.say(f"  ✗ {d['model']}: {d['evidence']}")
        rulings[jk] = radio(io, t, t("decide.rule"), [("confirmed", t("report.rl.confirmed")),
                                                     ("dismissed", t("report.rl.dismissed"))])
    return rulings


def available_plans(run: Run) -> list[str]:
    plans = []
    if run.path("09-plans/A.md").exists():
        plans.append("A")
    if run.path("09-plans/B.md").exists() and \
            read_json(run.path("09-plans/B.json"), default={}).get("recommendation") \
            in (None, "publish_revised"):
        plans.append("B")
    return plans


def write_final(run: Run, choice: str, manual_path: str | None = None) -> str:
    src = {"A": "09-plans/A.md", "B": "09-plans/B.md"}.get(choice)
    final = run.path("final.md")
    if choice == "hold":
        return ""
    if choice == "manual":
        if manual_path:
            shutil.copyfile(manual_path, final)
        elif not final.exists() and run.path("09-plans/A.md").exists():
            shutil.copyfile(run.path("09-plans/A.md"), final)
    elif src:
        shutil.copyfile(run.path(src), final)
    return str(final)


def record_decision(run: Run, *, choice: str, rulings: dict[str, str], final_path: str | None,
                    brand: str) -> dict:
    prev = read_json(run.path("10-decision.json"), default={})
    rul = dict(prev.get("rulings", {}))
    rul.update(rulings)
    dec = {"choice": choice, "rulings": rul, "final": final_path, "brand": brand,
           "decided_at": datetime.now().isoformat(timespec="seconds")}
    write_json(run.path("10-decision.json"), dec)
    return dec


def style_candidates(store: Store, run: Run, brand: str, min_repeats: int) -> list[dict]:
    """Log this run's style corrections, return (from,to) pairs seen >= min_repeats times."""
    corrections = read_json(run.path("09-plans/corrections.json"), default=[])
    log = read_jsonl(store.corrections_log)
    logged_here = {(e["from"], e["to"]) for e in log if e.get("run") == run.id}
    for c in corrections:
        if c.get("category") in STYLE_CATEGORIES and (c["from"], c["to"]) not in logged_here:
            append_jsonl(store.corrections_log, {"brand": brand, "run": run.id, "from": c["from"],
                                                 "to": c["to"], "category": c["category"]})
            logged_here.add((c["from"], c["to"]))
    log = read_jsonl(store.corrections_log)
    existing = guide_rules(store, brand)
    counts: dict[tuple[str, str], set[str]] = {}
    for e in log:
        if e["brand"] == brand:
            counts.setdefault((e["from"], e["to"]), set()).add(e["run"])
    return [{"from": f, "to": to, "runs": len(r)} for (f, to), r in counts.items()
            if len(r) >= min_repeats and (f, to) not in existing]


def guide_path(store: Store, brand: str):
    safe = re.sub(r"[^\w.-]+", "-", brand).strip("-") or "default"
    return store.style_guides / f"{safe}.md"


def guide_rules(store: Store, brand: str) -> set[tuple[str, str]]:
    p = guide_path(store, brand)
    if not p.exists():
        return set()
    return set(re.findall(r'^- "(.+?)" -> "(.+?)"', p.read_text(encoding="utf-8"), re.M))


def guide_text(store: Store, brand: str) -> str:
    p = guide_path(store, brand)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def write_style_rules(store: Store, brand: str, rules: list[dict]) -> None:
    p = guide_path(store, brand)
    text = p.read_text(encoding="utf-8") if p.exists() else f"# Style guide: {brand}\n\n"
    for r in rules:
        f, to = (" ".join(str(r[k]).split()).replace('"', "'") for k in ("from", "to"))
        text += f'- "{f}" -> "{to}"  (seen in {r["runs"]} runs)\n'
    write_text_atomic(p, text)


def propose_style_rules(io: IO, t: T, store: Store, run: Run, brand: str,
                        min_repeats: int) -> list[dict]:
    cands = style_candidates(store, run, brand, min_repeats)
    if not cands:
        return []
    io.say(t("decide.style_proposal", brand=brand))
    for c in cands:
        io.say(f'  "{c["from"]}" -> "{c["to"]}" ({c["runs"]})')
    if confirm(io, t, t("decide.style_confirm"), default=False):
        write_style_rules(store, brand, cands)
        return cands
    return []


def run_decision(io: IO | None, run: Run, store: Store, *, models: list[str], lang: str,
                 thresholds: dict[str, float], min_repeats: int, choice: str | None = None,
                 rulings: dict[str, str] | None = None, manual_path: str | None = None) -> dict:
    """Interactive when io is given and an argument is missing; otherwise from arguments.
    A bare red-line key in rulings applies to every jurisdiction where it is pending."""
    from .refresh import compute_synthesis
    from .report import write_report
    t = T(lang)
    intake = read_json(run.path("00-intake.json"))
    brand = intake.get("card", {}).get("org") or "default"
    syn = read_json(run.path("06-synthesis.json"))
    pending = pending_rulings(syn)
    given = {}
    for k, v in (rulings or {}).items():
        for jk in pending:
            if jk == k or jk.split(":", 1)[1] == k:
                given[jk] = v
    missing = [k for k in pending if k not in given]
    if missing and io is not None:
        given.update(ask_rulings(io, t, syn, missing))
    if given:
        record_decision(run, choice="pending", rulings=given, final_path=None, brand=brand)
        syn = compute_synthesis(run, models, thresholds)
        write_report(run, syn, lang=lang, changelog=[f"ruling {k}: {v}" for k, v in given.items()])
    plans = available_plans(run)
    options = plans + ["manual", "hold"]
    if choice is None:
        if io is None:
            raise ValueError("--choice is required in non-interactive mode")
        opts = [(p, t(f"decide.plan.{p}")) for p in options]
        default = "hold" if syn["consolidated"]["verdict"] == "no_go" else (plans or ["hold"])[0]
        choice = radio(io, t, t("decide.choose"), opts, default=default)
        if choice == "manual" and manual_path is None:
            manual_path = io.ask(t("decide.manual_path") + " ").strip() or None
    if choice not in options:
        raise ValueError(f"choice must be one of {options}")
    final = write_final(run, choice, manual_path)
    dec = record_decision(run, choice=choice, rulings=given, final_path=final or None,
                          brand=brand)
    if io is not None and choice != "hold":
        dec["style_rules"] = propose_style_rules(io, t, store, run, brand, min_repeats)
        write_json(run.path("10-decision.json"), dec)
    return dec
