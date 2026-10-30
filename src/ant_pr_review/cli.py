"""ant-pr-review command line."""
from __future__ import annotations

import argparse
import re
import shutil
import sys

from . import __version__
from .backends.base import get_backend
from .catalog import DEPTHS, DIRECTIONS, LENSES, POSTURES, SIGNALS
from .decision import run_decision
from .i18n import T
from .intake import CHANNELS, STAKEHOLDERS, build_intake_from_args, run_intake_interactive, split_list
from .jsonio import read_json, write_json
from .lessons import add_lesson, all_lessons, archive_lesson, lessons_for, promote_if_repeated
from .onboarding import banner, choose_lang, choose_models, effective_models, first_use
from .pipeline import Ctx, run_pipeline
from .refresh import factcheck_continue
from .store import BACKENDS, LANGS, Config, Store
from .ui import IO, ConsoleIO, checkbox, confirm, info, radio, section
from .workspace import PHASES, Run, create_run, list_runs, unfinished_runs

EXIT_OK, EXIT_PAUSED, EXIT_USAGE, EXIT_INTERRUPTED = 0, 3, 2, 130


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ant-pr-review",
                                description="Multi-model, multi-vendor PR publishing and "
                                            "operations risk review.")
    p.add_argument("--version", action="version", version=__version__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--models", help="one-off roster, e.g. claude:opus,openai:gpt-5 (not saved)")
    common.add_argument("--backend", choices=BACKENDS + ["fake"], help="one-off backend")
    common.add_argument("--lang", choices=LANGS, help="one-off interface language")
    common.add_argument("--yes", "-y", action="store_true",
                        help="non-interactive: accept defaults, never prompt")
    sub = p.add_subparsers(dest="cmd")

    n = sub.add_parser("new", parents=[common], help="start a new run (default command)")
    n.add_argument("--purpose", choices=["audit", "drafting"], default="audit",
                   help="audit content we have (default) or draft our statement from --brief")
    n.add_argument("--brief", help="drafting: the brief as a .json or .toml file (D-0005); "
                                   "--target is then material read only to check facts")
    n.add_argument("--direction", choices=DIRECTIONS)
    n.add_argument("--role", action="append", default=[],
                   help="our identity <standpoint>:<party>, e.g. responsible:organization, "
                        "affected:victims (repeat; default responsible:organization)")
    n.add_argument("--posture", choices=POSTURES, help="default clarify_apologize")
    n.add_argument("--means", help="comma list of white,gray,black (default all; black is "
                                   "assessed, never scheduled)")
    n.add_argument("--target", action="append", default=[], help="URL, path or text (repeat)")
    n.add_argument("--jurisdictions", help="comma list of tw,us,eu,cn (default tw)")
    n.add_argument("--depth", choices=DEPTHS)
    n.add_argument("--lenses", help="comma list, default per direction: " + ",".join(LENSES))
    n.add_argument("--org", default="", help="our organisation or brand")
    n.add_argument("--tax-id", default="", help="our Taiwan tax ID (統一編號) for the registry lookup")
    n.add_argument("--company-lookup", action="store_true",
                   help="with --yes: look up the registry and search competitors (D-0004)")
    n.add_argument("--party", action="append", default=[], help="a named party (repeat)")
    n.add_argument("--channels", help="comma list: " + ",".join(CHANNELS) + " or custom:<text>")
    n.add_argument("--stakeholders", help="comma list: " + ",".join(STAKEHOLDERS))
    n.add_argument("--publish-at", default="", help="planned publish date, YYYY-MM-DD")
    n.add_argument("--keywords", help="topic keywords for the context scan")
    n.add_argument("--speaker", default="", help="who publishes it, and in what role")
    n.add_argument("--background", default="", help="known disputes or background")
    n.add_argument("--locked", action="append", default=[],
                   help="a sentence plan A must not change (repeat)")
    n.add_argument("--focus", default="", help="what to look at most closely")
    n.add_argument("--embargo", action="store_true", help="no web calls at all (D-PR-9)")
    n.add_argument("--academic", action="store_true",
                   help="check DOIs and arXiv ids against doi.org, Crossref and arXiv")
    n.add_argument("--signals", help="observed event signals, comma list (D-0006): "
                   + ",".join(SIGNALS))
    n.add_argument("--characterised", action="store_true",
                   help="the cause and scope are confirmed (an audit; drafting uses its brief)")
    n.add_argument("--occurred-at", default="", help="when the event happened (D-0007)")
    n.add_argument("--known-at", default="", help="when we first knew internally")
    n.add_argument("--exposed-at", default="", help="when it first became public")
    n.add_argument("--export", action="store_true",
                   help="also write PDF and DOCX of the final text (needs the export extra)")
    n.add_argument("--context-scan", action="store_true",
                   help="with --yes: run the web context scan without asking")
    n.add_argument("--merger", help="the model that merges jurisdictions (default: first)")
    n.add_argument("--archive-on-block", action="store_true",
                   help="when a site refuses us (403 or a bot challenge), read its Wayback copy")
    n.add_argument("--no-render", action="store_true",
                   help="never use the headless browser for JavaScript-rendered pages")
    n.add_argument("--feed-limit", type=int, default=None,
                   help="for an RSS/Atom target: review the newest N articles, one run each "
                        "(default 1 with --yes)")

    r = sub.add_parser("resume", parents=[common], help="continue a run")
    r.add_argument("run")
    r.add_argument("--company-lookup", action="store_true",
                   help="with --yes: allow the registry lookup and competitor search")
    rr = sub.add_parser("rerun", parents=[common], help="redo a run from a phase")
    rr.add_argument("run")
    rr.add_argument("--from", dest="phase", choices=PHASES, required=True)
    rr.add_argument("--company-lookup", action="store_true",
                    help="with --yes: allow the registry lookup and competitor search")

    f = sub.add_parser("factcheck", parents=[common], help="retry unfinished fact checks")
    f.add_argument("run")
    f.add_argument("--continue", dest="cont", action="store_true", required=True)
    f.add_argument("--finalize", action="store_true",
                   help="with --yes: finalize instead of saving for later")
    f.add_argument("--lift-embargo", action="store_true",
                   help="the material is public now: allow web checks for this run")

    d = sub.add_parser("decide", parents=[common], help="rule red lines and choose a plan")
    d.add_argument("run")
    d.add_argument("--choice", choices=["A", "B", "manual", "hold"])
    d.add_argument("--rule", action="append", default=[],
                   help="[<jurisdiction>:]<red_line>=confirmed|dismissed")
    d.add_argument("--file", help="your own final file for --choice manual")

    c = sub.add_parser("config", parents=[common], help="change saved settings")
    c.add_argument("what", choices=["models", "lang", "show"])

    ls = sub.add_parser("lessons", parents=[common], help="user lessons")
    ls.add_argument("action", choices=["new", "list", "archive"])
    ls.add_argument("arg", nargs="?", help="title for new, id for archive")
    ls.add_argument("--area", default="")
    ls.add_argument("--cause")
    ls.add_argument("--rule", dest="lrule")
    ls.add_argument("--enforced")
    ls.add_argument("--archived", action="store_true")

    rs = sub.add_parser("runs", parents=[common], help="list runs and their status")
    rs.add_argument("--summary", action="store_true", help="one row per run: verdict, red lines")
    rs.add_argument("--format", choices=["md", "csv"], default="md")
    rs.add_argument("--out", help="write the summary to this file instead of the screen")
    return p


def find_run(store: Store, ref: str) -> Run:
    runs = list_runs(store.runs_dir)
    if ref == "latest" and runs:
        return runs[-1]
    exact = [r for r in runs if r.id == ref]
    if exact:
        return exact[0]
    pref = [r for r in runs if r.id.startswith(ref)]
    if len(pref) == 1:
        return pref[0]
    raise SystemExit(f"run not found or ambiguous: {ref}")


def slug_for(target: str) -> str:
    """A short readable name for the run folder from its first target."""
    from pathlib import Path
    from urllib.parse import urlsplit
    s = target.strip()
    if re.match(r"https?://", s, re.I):
        u = urlsplit(s)
        last = [p for p in u.path.split("/") if p][-1:] or [""]
        return f"{u.hostname or 'url'} {Path(last[0]).stem}".strip()
    first = s.splitlines()[0] if s else "run"
    looks_like_path = "\n" not in s and " " not in s and ("/" in s or "\\" in s)
    if len(s) < 4096 and (looks_like_path or ("\n" not in s and Path(s).expanduser().exists())):
        return Path(s).stem or Path(s).name
    return first.lstrip("#").strip()[:40] or "run"


def make_feed_crawler(store: Store):
    from .pipeline import make_crawler
    return make_crawler(store)


def split_feeds(io: IO, t: T, intake: dict, store: Store, *, interactive: bool,
                limit: int | None) -> list[dict]:
    """Turn each RSS/Atom URL into chosen articles; every article becomes its own intake.
    Non-feed targets stay together in one intake, as before. A drafting run has no
    targets: its material stays with its one brief (D-0005)."""
    if intake.get("purpose") == "drafting":
        return [intake]
    from .sources.crawler import FetchError
    from .sources.feeds import FEED_TYPES, parse_feed
    crawler = make_feed_crawler(store)
    plain, articles = [], []
    for tgt in intake["targets"]:
        if tgt["kind"] != "url":
            plain.append(tgt)
            continue
        try:
            res = crawler.fetch(tgt["value"])
        except FetchError:
            plain.append(tgt)  # the sources phase reports the failure
            continue
        if res.content_type not in FEED_TYPES:
            plain.append(tgt)
            continue
        try:
            items = parse_feed(res.body)
        except ValueError:
            plain.append(tgt)
            continue
        if interactive:
            opts = [(str(i), f"{it['title']}" + (f"  ({it['date']})" if it["date"] else ""))
                    for i, it in enumerate(items)]
            picked = [items[int(i)] for i in checkbox(io, t, t("feed.pick", n=len(items)), opts,
                                                     [], min_selected=1)]
        else:
            picked = items[:max(1, limit or 1)]
            io.say(info(t("feed.picked", n=len(picked), total=len(items))))
        articles += [{"kind": "feed_item", "value": it["link"], "title": it["title"],
                      "html": it["html"]} for it in picked]
    out = [dict(intake, targets=plain)] if plain else []
    out += [dict(intake, targets=[a]) for a in articles]
    return out


def load_cfg(args, io: IO, store: Store) -> Config:
    if getattr(args, "yes", False):
        cfg = store.load_config()
        if not cfg.configured:
            store.save_config(cfg)
    else:
        cfg = first_use(io, store, get_backend)
    if args.lang:
        cfg.lang = args.lang
    return cfg


def make_ctx(args, io: IO, store: Store, cfg: Config, *, models=None, backend=None,
             lang=None) -> Ctx:
    backend_name = backend or args.backend or cfg.backend
    lenses = split_list(getattr(args, "lenses", None) or "")
    bad = [ln for ln in lenses if ln not in LENSES]
    if bad:
        raise SystemExit(f"unknown lens(es) {bad}; choose from {list(LENSES)}")
    models = models or effective_models(cfg, args.models)
    merger = getattr(args, "merger", None)
    if merger:
        from .roster import normalize
        merger = normalize(merger)
        if merger not in models:
            raise SystemExit(f"--merger must be one of the roster: {models}")
    return Ctx(io=io, store=store, cfg=cfg, backend=get_backend(backend_name),
               models=models, lang=lang or cfg.lang, interactive=not args.yes,
               options={"depth": getattr(args, "depth", None), "lenses": lenses or None,
                        "context_scan": getattr(args, "context_scan", False),
                        "company_lookup": getattr(args, "company_lookup", False),
                        "merger": merger,
                        **({"renderer": None} if getattr(args, "no_render", False) else {}),
                        **({"archive_on_block": True}
                           if getattr(args, "archive_on_block", False) else {})})


def run_ctx(args, io: IO, store: Store, cfg: Config, run: Run) -> Ctx:
    """A resumed run uses the models/backend/lang recorded at creation (N-run-workspace-001)."""
    models, backend, lang = run.settings()
    return make_ctx(args, io, store, cfg, models=models, backend=backend,
                    lang=args.lang or lang)


def finish(status: str) -> int:
    return {"done": EXIT_OK, "paused": EXIT_PAUSED, "interrupted": EXIT_INTERRUPTED}[status]


def _delete_menu(io: IO, t: T, pending: list[Run]) -> None:
    """Pick an unfinished run, show what is in it, delete only after confirmation."""
    rid = radio(io, t, t("run.delete_which"),
                [(r.id, f"{r.id} ({r.first_incomplete()})") for r in pending])
    run = next(r for r in pending if r.id == rid)
    n = sum(1 for p in run.root.rglob("*") if p.is_file())
    if confirm(io, t, t("run.delete_confirm", run=run.id, n=n), default=False):
        shutil.rmtree(run.root)
        io.say(t("run.deleted", run=run.id))


def cmd_new(args, io: IO, store: Store, cfg: Config) -> int:
    t = T(cfg.lang)
    if not args.yes and not args.target:
        while pending := unfinished_runs(store.runs_dir):
            io.say(section(t("run.resume_found")))
            opts = []
            for r in pending[-5:]:
                opts.append((f"c:{r.id}", t("run.resume.continue", run=r.id,
                                            phase=r.first_incomplete())))
            opts.append(("delete", t("run.resume.delete")))
            opts.append(("new", t("run.resume.new")))
            choice = radio(io, t, t("run.resume_choice"), opts, default="new")
            if choice == "delete":
                _delete_menu(io, t, pending)
                continue
            if choice.startswith("c:"):
                run = find_run(store, choice[2:])
                ctx = run_ctx(args, io, store, cfg, run)
                io.say(banner(ctx.t, ctx.models))
                return finish(run_pipeline(run, ctx))
            break
    ctx = make_ctx(args, io, store, cfg)
    io.say(banner(ctx.t, ctx.models))
    if args.target or args.yes or args.brief:
        try:
            brief = None
            if args.brief:
                from .drafting import load_brief
                try:
                    brief = load_brief(args.brief)
                except (OSError, ValueError) as e:  # JSON and TOML errors are ValueErrors
                    raise ValueError(f"cannot read --brief {args.brief}: {e}") from e
            intake = build_intake_from_args(
                args.direction or "outbound", args.target, lang=ctx.lang,
                jurisdictions=args.jurisdictions, org=args.org, parties=args.party,
                channels=args.channels, stakeholders=args.stakeholders,
                publish_at=args.publish_at, keywords=args.keywords, embargo=args.embargo,
                posture=args.posture, means=args.means, speaker=args.speaker,
                background=args.background, locked=args.locked, focus=args.focus,
                roles=args.role or None, tax_id=args.tax_id,
                purpose="drafting" if args.brief and args.purpose == "audit" else args.purpose,
                brief=brief, signals=args.signals, characterised=args.characterised,
                academic=args.academic, occurred_at=args.occurred_at, known_at=args.known_at,
                exposed_at=args.exposed_at, export=args.export)
        except ValueError as e:
            io.say(f"error: {e}")
            return EXIT_USAGE
    else:
        # Ask everything first: leaving midway must not leave an empty run behind.
        intake = run_intake_interactive(io, ctx.t, ctx.lang)
    intakes = split_feeds(io, ctx.t, intake, store, interactive=not args.yes,
                          limit=args.feed_limit)
    runs = []
    for it in intakes:
        if it.get("purpose") == "drafting":  # no target: named after the first fact
            slug = "draft-" + slug_for(it["brief"]["facts"][0]["text"])
        else:
            first = it["targets"][0]
            slug = first.get("title") or slug_for(first["value"])
        run = create_run(store.runs_dir, slug, models=ctx.models, backend=ctx.backend.name,
                         lang=ctx.lang)
        io.say(ctx.t("run.created", path=str(run.root)))
        write_json(run.path("00-intake.json"), it)
        run.mark("intake", "done")  # answered before the folder existed
        runs.append(run)
    worst = "done"
    for run in runs:
        status = run_pipeline(run, ctx)
        if status == "interrupted":
            return finish(status)
        if status == "paused":
            worst = "paused"
    return finish(worst)


def cmd_resume(args, io, store, cfg) -> int:
    run = find_run(store, args.run)
    ctx = run_ctx(args, io, store, cfg, run)
    io.say(banner(ctx.t, ctx.models))
    return finish(run_pipeline(run, ctx))


def cmd_rerun(args, io, store, cfg) -> int:
    run = find_run(store, args.run)
    run.rerun_from(args.phase)
    order = PHASES.index(args.phase)
    for phase, folder in (("review", "04-reviews"), ("debate", "05-debate"),
                          ("jmerge", "07-jmerge")):
        if order <= PHASES.index(phase) and run.path(folder).exists():
            shutil.rmtree(run.path(folder))
    if order <= PHASES.index("draft"):  # D-0005: write afresh, never replay the cache
        run.path("08-drafts/writer.json").unlink(missing_ok=True)
    return cmd_resume(args, io, store, cfg)


def cmd_factcheck(args, io, store, cfg) -> int:
    run = find_run(store, args.run)
    ctx = run_ctx(args, io, store, cfg, run)
    if args.lift_embargo:
        st = run.state()
        st["embargo_lifted"] = True
        run.save_state(st)
    if args.yes:
        from .factcheck import pick_checker, run_checks
        from .refresh import factcheck_blocked, finalize_factcheck
        from .scholarly import verify_identifiers
        verify_identifiers(run, say=io.say)
        s = run_checks(run, ctx.backend, pick_checker(ctx.models, ctx.models), ctx.lang,
                       blocked=factcheck_blocked(run), say=io.say)
        io.say(ctx.t("fc.summary", done=s["done"], total=s["total"], left=s["left"],
                     reasons=", ".join(f"{k} {v}" for k, v in s["reasons"].items())))
        if s["left"] and not args.finalize:
            io.say(ctx.t("fc.resume_hint", run=run.id))
            return EXIT_PAUSED
        status, meta = finalize_factcheck(run, ctx.models, cfg.thresholds, ctx.lang)
        io.say(ctx.t(f"fc.{status}", v=(meta or {}).get("version", 0), run=run.id))
        return EXIT_OK
    status = factcheck_continue(run, ctx.backend, ctx.models, cfg.thresholds, ctx.lang, io)
    return EXIT_PAUSED if status == "later" else EXIT_OK


def cmd_decide(args, io, store, cfg) -> int:
    run = find_run(store, args.run)
    ctx = run_ctx(args, io, store, cfg, run)
    rulings = {}
    for r in args.rule:
        k, _, v = r.partition("=")
        if v not in ("confirmed", "dismissed"):
            io.say("error: --rule needs [<jurisdiction>:]<red_line>=confirmed|dismissed")
            return EXIT_USAGE
        rulings[k] = v
    try:
        run_decision(None if args.yes else io, run, store, models=ctx.models, lang=ctx.lang,
                     thresholds=cfg.thresholds, min_repeats=cfg.style_guide_min_repeats,
                     choice=args.choice, rulings=rulings, manual_path=args.file)
    except ValueError as e:
        io.say(f"error: {e}")
        return EXIT_USAGE
    run.mark("decision", "done")
    io.say(ctx.t("run.done", path=str(run.root)))
    return EXIT_OK


def cmd_config(args, io, store, cfg) -> int:
    if args.what == "show":
        io.say(store.config_path.read_text() if store.config_path.exists() else "(no config)")
        return EXIT_OK
    if args.what == "models":
        choose_models(io, cfg, get_backend(args.backend or cfg.backend))
    else:
        choose_lang(io, cfg)
    store.save_config(cfg)
    io.say(T(cfg.lang)("setup.saved", path=str(store.config_path)))
    io.say(banner(T(cfg.lang), cfg.models))
    return EXIT_OK


def cmd_lessons(args, io, store, cfg) -> int:
    t = T(cfg.lang)
    if args.action == "list":
        for ls in (lessons_for(store, args.area) if args.area else all_lessons(store)):
            io.say(f"{ls['id']}  [{ls['area']}]  {ls['title']}  — {ls['rule']}")
        return EXIT_OK
    if args.action == "archive":
        archive_lesson(store, args.arg)
        return EXIT_OK
    if not args.arg:
        io.say('error: lessons new "<title>"')
        return EXIT_USAGE
    area = args.area or ("" if args.yes else io.ask(t("lessons.area") + " ").strip())
    cause = args.cause or ("" if args.yes else io.ask(t("lessons.cause") + " ").strip())
    rule = args.lrule or ("" if args.yes else io.ask(t("lessons.rule") + " ").strip())
    enforced = args.enforced or ("judgment" if args.yes else
                                 io.ask(t("lessons.enforced") + " ").strip() or "judgment")
    lid = add_lesson(store, args.arg, area=area, cause=cause, rule=rule, enforced=enforced,
                     archived=args.archived)
    io.say(t("lessons.added", id=lid))
    if not args.yes:
        promote_if_repeated(io, t, store, lid, area)
    return EXIT_OK


def summary_rows(store: Store) -> list[dict]:
    from .report import latest_version
    rows = []
    for r in list_runs(store.runs_dir):
        intake = read_json(r.path("00-intake.json"), default={})
        facts = (intake.get("brief") or {}).get("facts") or [{}]
        first = (intake.get("targets") or [{"value": facts[0].get("text", "")}])[0]
        title = first.get("title") or (first.get("value", "").strip().splitlines() or [""])[0]
        title = title.lstrip("# ").strip()[:60]
        v = latest_version(r)
        meta = read_json(r.path(f"08-report.v{v}.json"), default={}) if v else {}
        red = sorted({f"{j}:{k}" for j, d in meta.get("red_lines", {}).items()
                      for k, s in d.items() if s == "confirmed"})
        nxt = r.first_incomplete()
        rows.append({"run": r.id, "title": title, "direction": intake.get("direction", ""),
                     "report": f"v{v}" if v else "", "verdict": meta.get("verdict", ""),
                     "red_lines": " ".join(red), "risks": meta.get("risks", ""),
                     "next": nxt or "done"})
    return rows


def cmd_runs(args, io, store, cfg) -> int:
    if args.summary:
        import csv
        import io as _io
        rows = summary_rows(store)
        cols = ["run", "title", "direction", "report", "verdict", "red_lines", "risks", "next"]
        if args.format == "csv":
            buf = _io.StringIO()
            w = csv.DictWriter(buf, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
            text = buf.getvalue()
        else:
            from .report import cell
            lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            lines += ["| " + " | ".join(cell(row[c]) if c == "title" else str(row[c])
                                        for c in cols) + " |" for row in rows]
            text = "\n".join(lines) + "\n"
        if args.out:
            from pathlib import Path
            from .jsonio import write_text_atomic
            write_text_atomic(Path(args.out), text)
            io.say(T(cfg.lang)("setup.saved", path=args.out))
        else:
            io.say(text.rstrip("\n"))
        return EXIT_OK
    for r in list_runs(store.runs_dir):
        nxt = r.first_incomplete()
        intake = read_json(r.path("00-intake.json"), default={})
        io.say(f"{r.id}  {intake.get('direction', '?'):9}  "
               + (f"next: {nxt}" if nxt else "done"))
    return EXIT_OK


COMMANDS = {"new": cmd_new, "resume": cmd_resume, "rerun": cmd_rerun,
            "factcheck": cmd_factcheck, "decide": cmd_decide, "config": cmd_config,
            "lessons": cmd_lessons, "runs": cmd_runs}


def main(argv: list[str] | None = None, *, io: IO | None = None,
         store: Store | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version"):
        argv = ["new"] + argv
    args = build_parser().parse_args(argv)
    io = io or ConsoleIO()
    store = store or Store()
    try:
        cfg = load_cfg(args, io, store)
        return COMMANDS[args.cmd](args, io, store, cfg)
    except (KeyboardInterrupt, EOFError):
        io.say("\n(interrupted)")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    raise SystemExit(main())
