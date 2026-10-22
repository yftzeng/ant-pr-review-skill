"""Runs the phases of one run in order, skipping what is done and unchanged."""
from __future__ import annotations

from dataclasses import dataclass, field

from .backends.base import Backend, BackendError
from .catalog import DEFAULT_LENSES, DEPTHS, LENSES, plan_units
from .contextscan import base_context, build_queries, run_queries
from .decision import run_decision
from .factcheck import build_ledger, pick_checker, read_ledger, run_checks, write_ledger
from .i18n import T
from .intake import posture_of, run_intake_interactive
from .jmerge import run_jmerge
from .jsonio import read_json, write_json
from .plans import run_plans
from .reaudit import run_reaudit
from .refresh import compute_synthesis, factcheck_blocked
from .report import latest_version, write_report
from .review import failed_jobs, load_records, run_debate, run_round1
from .roster import can_search
from .sources.acquire import failed_items, run_sources
from .sources.crawler import Crawler
from .sources.render import default_renderer
from .store import Config, Store
from .ui import IO, ask_text, checkbox, collect_lines, confirm, info, phase_line, prompt, question, radio
from .workspace import PHASES, Run


class Stop(Exception):
    """Pause the run cleanly (resume later)."""


@dataclass
class Ctx:
    io: IO
    store: Store
    cfg: Config
    backend: Backend
    models: list[str]
    lang: str
    interactive: bool
    crawler: Crawler | None = None
    options: dict = field(default_factory=dict)

    @property
    def t(self) -> T:
        return T(self.lang)

    def say(self, text: str = "") -> None:
        self.io.say(text)


def make_crawler(store: Store) -> Crawler:
    return Crawler(site_profiles=read_json(store.site_profiles, default={}))


# ---- phases -----------------------------------------------------------------

def ph_intake(run: Run, ctx: Ctx) -> None:
    if run.path("00-intake.json").exists():
        return
    if not ctx.interactive:
        raise Stop("intake missing: pass --direction and --target")
    write_json(run.path("00-intake.json"), run_intake_interactive(ctx.io, ctx.t, ctx.lang))


def ph_sources(run: Run, ctx: Ctx) -> None:
    """D-PR-15: the crawler and its fallbacks run inside run_sources; what still fails can
    be retried, pasted by the user, skipped, or left for later."""
    crawler = ctx.crawler or make_crawler(ctx.store)
    renderer = ctx.options["renderer"] if "renderer" in ctx.options else default_renderer()
    consent: bool | set[int] = True if ctx.options.get("archive_on_block") else set()
    while True:
        manifest = run_sources(run, crawler, renderer=renderer, archive_on_block=consent,
                               on_progress=lambda e: ctx.say(
            f"  {'✓' if e['status'] == 'ok' else '✗'} #{e['item']} {' '.join(e['value'].split())[:70]}"
            + (f" ({e.get('reason')})" if e["status"] != "ok" else "")
            + (f" [{ctx.t('via.' + e['via'])}{' ' + e['archived_at'] if e.get('archived_at') else ''}]"
               if e.get("via", "direct") != "direct" else "")
            + (f" ⚠ {e['warning']}" if e.get("warning") else "")))
        bad = failed_items(manifest)
        ok_count = len(manifest["items"]) - len(bad)
        if not bad:
            return
        for b in bad:
            if b.get("kind") == "url":
                ctx.say(ctx.t("sources.lesson_hint", reason=b.get("reason")))
        urls = [b for b in bad if b.get("kind") in ("url", "feed_item")]
        blocked = [b for b in bad if b.get("blocked")]
        for b in blocked:
            ctx.say(ctx.t("sources.blocked", url=b["value"], reason=b.get("reason")) + (
                " " + ctx.t("sources.blocked_archive", date=b["archive_at"])
                if b.get("archive_at") else ""))
        if not ctx.interactive:
            if any(b.get("archive_at") for b in blocked):
                ctx.say(ctx.t("sources.blocked_hint"))
            if urls:
                ctx.say(ctx.t("sources.paste_hint"))
            if ok_count:
                return
            raise Stop("no source could be read")
        opts = [("retry", ctx.t("sources.retry"))]
        with_copy = [b for b in blocked if b.get("archive_at")]
        if with_copy:
            opts.append(("archive", ctx.t("sources.use_archive", n=len(with_copy))))
        if urls:
            opts.append(("paste", ctx.t("sources.paste")))
        opts += [("continue", ctx.t("sources.continue")), ("stop", ctx.t("sources.stop"))]
        act = radio(ctx.io, ctx.t, ctx.t("sources.failed", n=len(bad)), opts,
                    default="retry" if not ok_count else "continue")
        if act == "archive":
            consent = set(consent) | {b["item"] for b in with_copy}
            continue
        if act == "paste":
            paste_texts(run, ctx, urls)
            continue
        if act == "continue" and ok_count:
            return
        if act == "stop" or (act == "continue" and not ok_count):
            raise Stop("sources")


def paste_texts(run: Run, ctx: Ctx, items: list[dict]) -> None:
    """Replace each failed URL target by text the user pastes; the URL stays its origin."""
    intake = read_json(run.path("00-intake.json"))
    for it in items:
        url = intake["targets"][it["item"] - 1]["value"]  # the manifest shows it redacted
        ctx.say(question(ctx.t("sources.paste_for", url=it["value"])))
        lines = collect_lines(ctx.io, ctx.t, prompt(""), lambda s: "")
        if lines:
            intake["targets"][it["item"] - 1] = {"kind": "text", "value": "\n".join(lines),
                                                 "pasted_for": url}
    write_json(run.path("00-intake.json"), intake)


def ph_context(run: Run, ctx: Ctx) -> None:
    """Sensitive dates always; web news only with consent and never under embargo (D-PR-9)."""
    card = read_json(run.path("00-intake.json"))["card"]
    out = base_context(card)
    for d in out["sensitive_dates"]:
        ctx.say(info(ctx.t("context.date", date=d["date"], note=d["note"],
                           jur=ctx.t("jur." + d["jurisdiction"]))))
    queries = build_queries(card)
    searcher = next((m for m in ctx.models if can_search(m)), None)
    if card.get("embargo"):
        out["status"] = "embargo"
    elif not queries:
        out["status"] = "skipped"
    elif not searcher:
        out["status"] = "no_search_backend"
    else:
        allowed = ctx.options.get("context_scan", False)
        if ctx.interactive and not allowed:
            ctx.say(ctx.t("context.queries"))
            for q in queries:
                ctx.say(f"    · {q}")
            allowed = confirm(ctx.io, ctx.t, ctx.t("context.confirm"), default=True)
        if allowed:
            out["queries"] = queries
            out["findings"], out["errors"] = run_queries(ctx.backend, searcher, queries, ctx.lang,
                                                         say=ctx.say)
            out["status"] = "done"
        else:
            out["status"] = "skipped"
    ctx.say(ctx.t("context.status", status=ctx.t("context." + out["status"])))
    write_json(run.path("02-context.json"), out)


def call_estimate(units: list[dict], models: list[str], jurisdictions: list[str]) -> int:
    n = len(units) * len(models) * 2              # round 1 + debate
    if len(jurisdictions) > 1:
        n += 2 + len(jurisdictions) * len(models)  # compare + final + discussion
    return n


def ph_matrix(run: Run, ctx: Ctx) -> None:
    intake = read_json(run.path("00-intake.json"))
    direction, js = intake["direction"], intake["card"]["jurisdictions"]
    t = ctx.t
    depth = ctx.options.get("depth")
    lenses = ctx.options.get("lenses")
    while True:
        if not depth:
            depth = radio(ctx.io, t, t("matrix.depth"), [(d, t(f"depth.{d}.long")) for d in DEPTHS],
                          default="quick") if ctx.interactive else "quick"
        if not lenses:
            default = DEFAULT_LENSES[direction]
            lenses = checkbox(ctx.io, t, t("matrix.lenses"),
                              [(ln, t(f"lens.{ln}")) for ln in LENSES], default,
                              min_selected=1) if ctx.interactive else default
        units = plan_units(direction, lenses, js, depth, posture_of(intake))
        if not units:
            raise Stop("no checklist item applies to these lenses and direction")
        ctx.say(info(t("matrix.summary", units=len(units), models=len(ctx.models),
                       calls=call_estimate(units, ctx.models, js))))
        for u in units:
            ctx.say(f"    {u['id']:<22} {len(u['items']):>2} items × {len(ctx.models)} models")
        if not ctx.interactive or confirm(ctx.io, t, t("matrix.confirm"), default=True):
            break
        depth, lenses = None, None
    merger = ctx.options.get("merger") or ctx.models[0]
    write_json(run.path("03-matrix.json"), {"direction": direction, "depth": depth,
                                            "posture": posture_of(intake),
                                            "lenses": lenses, "jurisdictions": js,
                                            "units": units, "models": ctx.models,
                                            "merger": merger})


def _handle_failures(run: Run, ctx: Ctx, failed, label: str, retry) -> None:
    while True:
        bad = failed()
        if not bad:
            return
        ctx.say(ctx.t("review.failed", models=", ".join(bad)))
        if not ctx.interactive:
            ctx.say(ctx.t("review.continue_without", models=", ".join(bad)))
            return
        act = radio(ctx.io, ctx.t, ctx.t("run.resume_choice"), [
            ("retry", ctx.t("sources.retry")), ("continue", ctx.t("review.without")),
            ("stop", ctx.t("sources.stop"))], default="retry")
        if act == "retry":
            retry()
            continue
        if act == "continue":
            return
        raise Stop(label)


def ph_review(run: Run, ctx: Ctx) -> None:
    units = read_json(run.path("03-matrix.json"))["units"]
    retry = lambda: run_round1(run, ctx.backend, ctx.models, ctx.lang, say=ctx.say)
    retry()
    _handle_failures(run, ctx, lambda: failed_jobs(load_records(run, "04-reviews"), units,
                                                   ctx.models), "review", retry)
    recs = load_records(run, "04-reviews")
    if not any(r.get("status") == "ok" for r in recs.values()):
        raise Stop("no reviewer answered")


def ph_factcheck(run: Run, ctx: Ctx) -> None:
    ledger = build_ledger(load_records(run, "04-reviews"), read_ledger(run))
    write_ledger(run, ledger)
    checker = pick_checker(ctx.models, ctx.models)
    summ = run_checks(run, ctx.backend, checker, ctx.lang, blocked=factcheck_blocked(run),
                      say=ctx.say)
    if summ["left"]:
        reasons = ", ".join(f"{k} {v}" for k, v in summ["reasons"].items())
        ctx.say(ctx.t("fc.summary", done=summ["done"], total=summ["total"], left=summ["left"],
                      reasons=reasons))
        ctx.say(ctx.t("fc.resume_hint", run=run.id))


def ph_debate(run: Run, ctx: Ctx) -> None:
    run_debate(run, ctx.backend, ctx.models, ctx.lang, say=ctx.say)


def ph_synthesis(run: Run, ctx: Ctx) -> None:
    compute_synthesis(run, ctx.models, ctx.cfg.thresholds)


def ph_jmerge(run: Run, ctx: Ctx) -> None:
    merger = read_json(run.path("03-matrix.json")).get("merger") or ctx.models[0]
    run_jmerge(run, ctx.backend, merger, ctx.lang, say=ctx.say)


def ph_report(run: Run, ctx: Ctx) -> None:
    syn = read_json(run.path("06-synthesis.json"))
    meta = write_report(run, syn, lang=ctx.lang)
    t = ctx.t
    for f in meta["files"]:
        ctx.say(t("report.written", path=str(run.path(f))))
    for j, v in meta["verdicts"].items():
        ctx.say(f"  {t('jur.' + j)}: {t('verdict.' + v)}")
    c = syn["consolidated"]
    ctx.say(info(t("report.done", verdict=t("verdict." + c["verdict"])
                   + (f" ({t('report.provisional')})" if c["provisional"] else ""))))
    for p in meta["lint"]:
        ctx.say(f"  ⚠ lint: {p}")


def ph_plans(run: Run, ctx: Ctx) -> None:
    out = run_plans(run, ctx.backend, ctx.models, ctx.lang, say=ctx.say)
    for name, rep in out["ethics"].items():
        if rep["first"]:
            ctx.say(ctx.t("plans.ethics", plan=name, n=len(rep["first"]),
                          result=ctx.t("plans.ethics.redacted" if rep["redacted"]
                                       else "plans.ethics.fixed")))
    for w in out["warnings"]:
        ctx.say(f"  · {w}")
    for s in out.get("stages", []):
        if s["status"] not in ("ok", "skipped"):
            ctx.say(f"  ⚠ {ctx.t('plans.stage.not_reviewed', stage=s['stage'], reason=s['reason'])}")


def ph_reaudit(run: Run, ctx: Ctx) -> None:
    st = run_reaudit(run, ctx.backend, ctx.models, ctx.lang, ctx.cfg.thresholds, say=ctx.say)
    ctx.say(ctx.t("reaudit.status", status=ctx.t("reaudit." + st["status"])))


def ph_decision(run: Run, ctx: Ctx) -> None:
    if not ctx.interactive:
        ctx.say(ctx.t("decide.hint", run=run.id))
        raise Stop("awaiting decision")
    run_decision(ctx.io, run, ctx.store, models=ctx.models, lang=ctx.lang,
                 thresholds=ctx.cfg.thresholds, min_repeats=ctx.cfg.style_guide_min_repeats)


PHASE_FUNCS = {
    "intake": ph_intake, "sources": ph_sources, "context": ph_context, "matrix": ph_matrix,
    "review": ph_review, "factcheck": ph_factcheck, "debate": ph_debate,
    "synthesis": ph_synthesis, "jmerge": ph_jmerge, "plans": ph_plans, "reaudit": ph_reaudit,
    "report": ph_report, "decision": ph_decision,
}


def run_pipeline(run: Run, ctx: Ctx) -> str:
    """Returns 'done', 'paused' or 'interrupted'."""
    for ph in PHASES:
        if not run.needs_run(ph):
            continue
        ctx.say(phase_line(ctx.t("run.phase_start", phase=ctx.t("phase." + ph))))
        run.mark(ph, "running")
        try:
            PHASE_FUNCS[ph](run, ctx)
        except BackendError as e:
            run.mark(ph, "pending")
            ctx.say(f"  ✗ {e}")
            ctx.say(ctx.t("run.resume_hint", run=run.id))
            return "paused"
        except Stop as e:
            run.mark(ph, "pending")
            ctx.say(ctx.t("run.paused", reason=str(e), run=run.id))
            return "paused"
        except KeyboardInterrupt:
            run.mark(ph, "pending")
            ctx.say(ctx.t("run.interrupted", run=run.id))
            return "interrupted"
        run.mark(ph, "done")
    ctx.say(ctx.t("run.done", path=str(run.root)))
    return "done"


__all__ = ["Ctx", "run_pipeline", "Stop", "make_crawler", "latest_version", "ask_text"]
