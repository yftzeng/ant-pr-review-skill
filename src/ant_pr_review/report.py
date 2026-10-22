"""Report: consolidated plus one per jurisdiction, versioned, with a linter."""
from __future__ import annotations

import re
from datetime import datetime

from . import ethics
from .factcheck import read_ledger, snapshot
from .i18n import T
from .catalog import item_index
from .intake import CARD_FIELDS, card_line
from .jsonio import read_json, write_json, write_text_atomic
from .workspace import Run

FIVE = ("anchor", "scenario", "standard", "why_it_matters", "mitigation")
UNVERIFIED_CLAIMS = re.compile(r"\b(?:I|we) (?:have )?(?:verified|ran|executed|tested|confirmed "
                               r"by running)\b|我(?:已|們已)?(?:驗證|执行|執行|驗算)過?", re.I)
# Tone rules after K-Dense lint_review: criticise the text, never the author.
TONE_RULES = {
    "abusive wording": re.compile(
        r"\b(?:idiot(?:ic)?|incompetent|ridiculous|nonsense|garbage|lazy|sloppy|clueless|"
        r"amateurish|embarrassing|worthless)\b|愚蠢|白癡|白痴|垃圾|草率|偷懶|外行|丟臉|丢脸|胡扯", re.I),
    "personal attack": re.compile(
        r"\b(?:the\s+)?(?:author|writer)s?\s+(?:do(?:es)?\s+not\s+understand|failed\s+to\s+"
        r"understand|(?:is|are)\s+(?:unaware|careless|dishonest|clueless))\b|"
        r"作者(?:根本|完全)?(?:不懂|不了解|不瞭解|很粗心|不誠實|不诚实)", re.I),
    "impersonation": re.compile(
        r"\b(?:i\s+am\s+(?:the\s+)?(?:editor|publisher)|on\s+behalf\s+of\s+the\s+"
        r"(?:editor|publication))\b|我是(?:總編|总编|編輯|编辑)", re.I),
    "editorial decision": re.compile(
        r"\b(?:i|we)\s+(?:recommend|would\s+recommend|have\s+decided)\s+"
        r"(?:to\s+)?(?:accept|reject)(?:ion|ance)?\b|建議(?:退稿|拒絕刊登)|建议(?:退稿|拒绝刊登)", re.I),
}
PLACEHOLDER = re.compile(r"TODO|TBD|\{\{|\}\}|<placeholder>|\[insert", re.I)


_MD_SPECIAL = re.compile(r"([\\`*_\[\]()!#|~])")


def cell(text) -> str:
    """Untrusted text as inert Markdown: HTML escaped, link/image/emphasis syntax escaped."""
    s = "" if text is None else str(text)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = _MD_SPECIAL.sub(r"\\\1", s)
    return " ".join(s.split())


def source_urls(sources: list[dict]) -> str:
    from .factcheck import norm_url
    out = []
    for s in sources:
        if not norm_url(s.get("url") or ""):
            continue
        u = s["url"].strip().replace("|", "%7C").replace("<", "%3C").replace(">", "%3E") \
            .replace(" ", "%20")
        date = str(s.get("accessed_at", ""))[:10]
        out.append(f"{u} ({date})" if date else u)
    return " ".join(out)


def latest_version(run: Run) -> int:
    vs = [int(m.group(1)) for p in run.root.glob("08-report.v*.json")
          if (m := re.match(r"08-report\.v(\d+)\.json$", p.name))]
    return max(vs, default=0)


def lint_report(syn: dict, md: str, flagged_excerpts: list[str]) -> list[str]:
    problems = []
    for f in syn["risks"] + syn["unverified"]:
        for k in FIVE:
            if not str(f.get(k, "")).strip():
                problems.append(f"{f.get('id', '?')}: empty field '{k}'")
        for k in FIVE:
            val = str(f.get(k, ""))
            if UNVERIFIED_CLAIMS.search(val):
                problems.append(f"{f.get('id', '?')}: unsupported verification claim in '{k}'")
            for name, rx in TONE_RULES.items():
                if rx.search(val):
                    problems.append(f"{f.get('id', '?')}: {name} in '{k}'")
            for h in ethics.scan_text(val):
                problems.append(f"{f.get('id', '?')}: ethics guard ({h['category']}) in '{k}', "
                                "redacted")
        anchor = str(f.get("anchor", ""))
        if anchor.lower().startswith("absence:") and "checked:" not in anchor.lower():
            problems.append(f"{f.get('id', '?')}: absence without checked surfaces")
    if PLACEHOLDER.search(md):
        problems.append("placeholder text left in report")
    headings = [ln for ln in md.splitlines() if ln.startswith("#")]
    for ex in flagged_excerpts:
        snippet = ex[:40]
        if snippet and any(snippet in h for h in headings):
            problems.append("flagged untrusted text used in a heading")
    return problems


def safe(text) -> str:
    """Report cell for reviewer text: evasion or persona advice is redacted (D-PR-7)."""
    s = str(text or "")
    hits = ethics.scan_text(s)
    return cell(ethics.redact(s, hits) if hits else s)


def _verdict(t: T, o: dict) -> str:
    v = t("verdict." + o["verdict"])
    return v + (f" ({t('report.provisional')})" if o.get("provisional") else "")


def heatmap(t: T, risks: list[dict]) -> list[str]:
    grid: dict[tuple[int, int], int] = {}
    for r in risks:
        k = (r["likelihood"], r["impact"])
        grid[k] = grid.get(k, 0) + 1
    out = [f"| {t('report.l_i')} | " + " | ".join(str(i) for i in range(1, 6)) + " |",
           "|---|" + "---:|" * 5]
    for lk in range(5, 0, -1):
        out.append(f"| **{lk}** | " + " | ".join(str(grid.get((lk, im), "·"))
                                                for im in range(1, 6)) + " |")
    return out


def _title(run: Run) -> str:
    manifest = read_json(run.path("01-sources/manifest.json"), default={"items": []})
    titles = [d.get("title") or d.get("origin") for it in manifest["items"]
              for d in it.get("docs", [])]
    return titles[0] if titles and titles[0] else run.id


def _risk_table(t: T, risks: list[dict]) -> list[str]:
    out = [f"| ID | {t('report.label')} | {t('report.unit')} | {t('report.location')} | "
           f"{t('report.dimension')} | L×I | {t('report.scenario')} | {t('report.standard')} | "
           f"{t('report.why')} | {t('report.mitigation')} | {t('report.supporters')} |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in risks:
        sp = r["spread"]
        li = f"{r['likelihood']}×{r['impact']}={r['score']}"
        if sp["likelihood"] or sp["impact"]:
            li += f" (±L{sp['likelihood']}/I{sp['impact']})"
        if r["wide"]:
            li += " **WIDE**"
        refs = f" [{'; '.join(r['legal_refs'])}]" if r["legal_refs"] else ""
        out.append(f"| {r['id']} | {r['label']} | {r['unit']} | {cell(r['anchor'])} | "
                   f"{t('dim.' + r['dimension'])} | {li} | {safe(r['scenario'])} | "
                   f"{safe(r['standard'])}{cell(refs)} | {safe(r['why_it_matters'])} | "
                   f"{safe(r['mitigation'])} | {', '.join(r['supporters'])} |")
    return out


MARK = {"pass": "✓", "concern": "⚠", "fail": "✗", "na": "–"}
UNANSWERED = "∅"


def bar(passed: int, applicable: int) -> str:
    """'███████░░░  67%  2/3'; n/a when no answer applies."""
    if not applicable:
        return "n/a"
    filled = int(10 * passed / applicable + 0.5)
    return (f"{'█' * filled}{'░' * (10 - filled)} {int(100 * passed / applicable + 0.5):>3}%  "
            f"{passed}/{applicable}")


def _counts(items: list[dict]) -> tuple[int, int]:
    vs = [v for i in items for v in i["by_model"].values() if v != "na"]
    return vs.count("pass"), len(vs)


def checklist_lines(t: T, items: list[dict], models: list[str]) -> list[str]:
    """D-0002: a checkbox list. Ticked only when every reviewer answered and every answer
    is pass or na; each line carries its pass-rate bar and every reviewer's mark."""
    idx = item_index()
    out = []
    for i in items:
        p, n = _counts([i])
        # A model of the roster with no answer (left the item out, or its whole unit
        # failed or was refused) is a gap: never a tick.
        missing = [m for m in models if m not in i["by_model"]]
        ticked = not missing and all(v in ("pass", "na") for v in i["by_model"].values())
        marks = " · ".join(f"{m} {MARK[i['by_model'][m]]}" if m in i["by_model"]
                           else f"{m} {UNANSWERED}" for m in models)
        gap = f" ({t('report.unanswered_n', n=len(missing))})" if missing else ""
        b = bar(p, n) + (f" {MARK[i['verdict']]}" if n else "")
        out.append(f"- [{'x' if ticked else ' '}] **{i['item']}** `{i['unit']}` `{b}`{gap} — "
                   f"{marks} — {cell(idx[i['item']]['text'][:90])}")
    if not items:
        return [t("report.none")]
    out += ["", f"**{t('report.subtotals')}**", ""]
    by_lens: dict[str, list[dict]] = {}
    by_scope: dict[str, list[dict]] = {}
    for i in items:
        by_lens.setdefault(idx[i["item"]]["lens"], []).append(i)
        by_scope.setdefault(i["unit"].split(".")[0], []).append(i)
    out += [f"- {t('lens.' + ln)} ({ln}): `{bar(*_counts(g))}`" for ln, g in by_lens.items()]
    out += [f"- {t('report.scope')} {sc}: `{bar(*_counts(g))}`" for sc, g in by_scope.items()]
    out += ["", f"**{t('report.overall_rate')}**: `{bar(*_counts(items))}`"]
    return out


def compare_lines(t: T, before: list[dict], after: list[dict]) -> list[str]:
    """Before -> after per (item, scope), then overall."""
    key = lambda i: (i["item"], i["unit"].split(".")[0])
    got = {key(i): i for i in after}
    out = []
    for i in before:
        a = got.get(key(i))
        before_c, after_c = _counts([i]), (_counts([a]) if a else None)
        moved = ""
        if after_c and before_c[1] and after_c[1]:
            d = after_c[0] / after_c[1] - before_c[0] / before_c[1]
            moved = " ▲" if d > 0 else (" ▼" if d < 0 else "")
        out.append(f"- **{i['item']}** `{key(i)[1]}` `{bar(*before_c)}` → "
                   f"`{bar(*after_c) if after_c else t('report.not_reaudited')}`{moved}")
    common = [i for i in before if key(i) in got]  # the same items on both sides
    out += ["", f"**{t('report.overall_rate')}**: `{bar(*_counts(common))}` → "
                f"`{bar(*_counts([got[key(i)] for i in common]))}`"]
    return out


def stage_lines(t: T, stages: list[dict]) -> list[str]:
    out = [f"| {t('report.stage')} | {t('report.writer')} | {t('report.reviewer')} | "
           f"{t('report.status')} | {t('report.result')} |", "|---|---|---|---|---|"]
    for s in stages:
        if s["status"] == "ok":
            st = "✓"
        elif s["status"] == "skipped":
            st = f"— {t('report.stage.skipped')} ({s['reason']})"
        else:
            st = f"⚠ **{t('report.stage.not_reviewed')}** ({s['reason']})"
        out.append(f"| {t('report.stage.' + s['stage'])} | {s['writer']} | {s['reviewer']} | "
                   f"{st} | {cell(s.get('result', ''))} |")
    return out


def _fenced(text: str) -> list[str]:
    fence = "`" * 3
    return [fence + "text", text.replace(fence, "'" * 3).rstrip("\n"), fence]


def _plans_sections(t: T, run: Run, scope: str | None) -> list[str]:
    from .reaudit import status as reaudit_status
    out: list[str] = []
    summary = read_json(run.path("09-plans/summary.json"), default={})
    if not summary:
        return out
    diff_p = run.path("09-plans/A.diff")
    if "A" in summary.get("plans", []):
        out += ["", f"## {t('report.revision')}", ""]
        diff = diff_p.read_text(encoding="utf-8") if diff_p.exists() else ""
        out += _fenced(diff) if diff.strip() else [t("report.revision_none")]
        a_p = run.path("09-plans/A.md")
        out += ["", f"### {t('report.revised_full')}", ""]
        out += _fenced(a_p.read_text(encoding="utf-8")) if a_p.exists() else [t("report.missing")]
        st = reaudit_status(run)
        after = read_json(run.path("09-plans/reaudit/06-synthesis.json"), default=None)
        if st["status"] == "done" and not after:
            st = {"status": "failed"}
        out += ["", f"### {t('report.reaudit')}", "",
                t("report.reaudit_note", status=t("reaudit." + st["status"])), ""]
        if st["status"] == "done":
            before = read_json(run.path("06-synthesis.json"))
            pick = (lambda syn: _consolidated_views(syn)["items"]) if scope is None else \
                (lambda syn: syn["jurisdictions"][scope]["items"])
            out += compare_lines(t, pick(before), pick(after))
            v = after["consolidated"] if scope is None else after["jurisdictions"][scope]
            out += ["", f"{t('report.verdict')}: {t('verdict.' + v['verdict'])} "
                        f"({t('report.reaudit_provisional')})"]
    tl_p = run.path("09-plans/T.md")
    if tl_p.exists():
        body = tl_p.read_text(encoding="utf-8").splitlines()[1:]
        out += ["", f"## {t('plans.t')}"]
        out += [("#" + ln) if ln.startswith("#") else ln for ln in body]
    if summary.get("stages"):
        out += ["", f"## {t('report.stages')}", "", t("report.stages_note"), ""]
        out += stage_lines(t, summary["stages"])
    return out


def _red_table_one(t: T, red: dict) -> list[str]:
    out = [f"| {t('report.red_line')} | {t('report.status')} | {t('report.severity')} | "
           f"{t('report.supporters')} | {t('report.dissent')} | {t('report.comment')} |",
           "|---|---|---|---|---|---|"]
    for k, v in red.items():
        if v["status"] == "clear":
            continue
        comment = "; ".join(f"{c['model']}: {c['comment']} {' '.join(c['anchors'])}"
                            for c in v["comments"])
        if v["evidence"]:
            comment += " " + "; ".join(f"{e['claim']}: {e['text']}" for e in v["evidence"])
        dissent = "; ".join(f"{d['model']}: {d['evidence']}" for d in v["dissent"])
        status = t("report.rl." + v["status"]) + (" ✋" if v.get("human_ruling") else "")
        out.append(f"| {t('redline.' + k)} | {status} | {v['severity']} | "
                   f"{', '.join(v['supporters'])} | {cell(dissent)} | {safe(comment)} |")
    if len(out) == 2:
        out.append(f"| {t('report.none')} | | | | | |")
    return out


def _consolidated_views(syn: dict) -> dict:
    os_ = list(syn["jurisdictions"].values())
    return {
        "risks": syn["risks"], "unver": syn["unverified"],
        "items": list({(i["item"], i["unit"]): i for o in os_ for i in o["items"]}.values()),
        "headlines": list(dict.fromkeys(h for o in os_ for h in o["headlines"])),
        "unanswered": list({(u["item"], u["unit"]): u for o in os_
                            for u in o["unanswered"]}.values()),
        "questions": list(dict.fromkeys(q for o in os_ for q in o["counsel_questions"])),
    }


def _verdict_section(t: T, syn: dict, scope: str | None) -> list[str]:
    out = ["", f"## {t('report.verdict_title')}", ""]
    if scope is not None:
        return out + [f"**{t('report.verdict')}: {_verdict(t, syn['jurisdictions'][scope])}**"]
    out += [f"| {t('report.jurisdiction')} | {t('report.verdict')} | {t('report.top_score')} | "
            f"{t('report.red_confirmed')} | {t('report.red_pending')} |", "|---|---|---:|---|---|"]
    for j, o in syn["jurisdictions"].items():
        top = max([r["score"] for r in o["risks"]] + [i["score"] for i in o["items"]], default=0)
        conf = [t("redline." + k) for k, v in o["red_lines"].items() if v["status"] == "confirmed"]
        pend = [t("redline." + k) for k, v in o["red_lines"].items()
                if v["status"] == "needs_ruling"]
        out.append(f"| {t('jur.' + j)} | {_verdict(t, o)} | {top} | {', '.join(conf) or '—'} | "
                   f"{', '.join(pend) or '—'} |")
    c = syn["consolidated"]
    return out + ["", f"**{t('report.overall')}: {_verdict(t, c)}**  "
                      f"({t('report.strictest')}: {', '.join(t('jur.' + j) for j in c['worst'])})"]


def _red_section(t: T, syn: dict, scope: str | None) -> list[str]:
    js = list(syn["jurisdictions"])
    out = ["", f"## {t('report.red_lines')}", ""]
    if scope is None and len(js) > 1:
        out += [f"| {t('report.red_line')} | " + " | ".join(t("jur." + j) for j in js) + " |",
                "|---|" + "---|" * len(js)]
        for k in syn["jurisdictions"][js[0]]["red_lines"]:
            sts = [syn["jurisdictions"][j]["red_lines"][k]["status"] for j in js]
            if set(sts) != {"clear"}:
                out.append(f"| {t('redline.' + k)} | "
                           + " | ".join(t("report.rl." + s) for s in sts) + " |")
        if len(out) == 5:
            out.append(f"| {t('report.none')} |" + " |" * len(js))
        return out
    return out + _red_table_one(t, syn["jurisdictions"][scope or js[0]]["red_lines"])


def _jmerge_section(t: T, jm: dict, js: list[str]) -> list[str]:
    if jm.get("status") != "ok":
        return []
    d = jm["data"]
    out = ["", f"## {t('report.jcompare')} ({t('report.merger')}: {jm.get('merger', '')})", "",
           safe(d["summary"])]
    if d["common_risks"]:
        out += ["", f"**{t('report.common')}**", ""] + [f"- {safe(x)}" for x in d["common_risks"]]
    if d["differences"]:
        out += ["", f"| {t('report.topic')} | " + " | ".join(t("jur." + j) for j in js) + " |",
                "|---|" + "---|" * len(js)]
        for diff in d["differences"]:
            pos = {b["jurisdiction"].strip().lower(): b["position"] for b in diff["by_jurisdiction"]}
            out.append(f"| {safe(diff['topic'])} | "
                       + " | ".join(safe(pos.get(j, "—")) for j in js) + " |")
    out += ["", f"{t('report.strictest')}: {safe(d['strictest'])}", ""]
    out += [f"- **{t('jur.' + n['jurisdiction'].strip().lower())}**: {safe(n['note'])}"
            for n in d["notes"] if n["jurisdiction"].strip().lower() in js]
    return out


def render(run: Run, syn: dict, *, lang: str, version: int, changelog: list[str],
           scope: str | None = None) -> str:
    """scope None = consolidated; otherwise one jurisdiction."""
    t = T(lang)
    intake = read_json(run.path("00-intake.json"))
    matrix = read_json(run.path("03-matrix.json"))
    context = read_json(run.path("02-context.json"), default={})
    ledger = read_ledger(run)
    scan = read_json(run.path("01-sources/injection-scan.json"), default={"flags": []})
    jm = read_json(run.path("07-jmerge/final.json"), default={})
    models = [p["model"] for p in syn["provenance"]]
    js = list(syn["jurisdictions"])
    label = t("report.consolidated") if scope is None else t("jur." + scope)
    L = [f"# {t('report.title')} — {cell(_title(run))} · {label} (v{version})", ""]
    L.append(f"- {t('report.run')}: `{run.id}`  ·  {datetime.now():%Y-%m-%d %H:%M}")
    L.append(f"- {t('report.direction')}: {t('intake.direction.' + intake['direction'])}")
    card = intake.get("card", {})
    L += [f"- {t('card.' + f + '.label')}: {cell(card_line(t, f, card))}" for f in CARD_FIELDS]
    manifest = read_json(run.path("01-sources/manifest.json"), default={"items": []})
    for it in manifest["items"]:
        if it.get("status") != "ok" or it.get("kind") == "text" and not it.get("via"):
            continue
        via = it.get("via", "direct")
        note = t("via." + via) + (f" {it['archived_at']}" if it.get("archived_at") else "")
        if it.get("fell_back_from"):
            note += f" ← {it['fell_back_from']}"
        origin = it.get("archive_url") or it.get("final_url") or it["value"]
        L.append(f"- {t('report.source')} #{it['item']}: {cell(origin)} ({cell(note)})")
    L.append(f"- {t('report.depth')}: {t('depth.' + matrix['depth'])} · "
             f"{t('report.units')}: {len(matrix['units'])} × {len(models)}")
    L += ["", f"> {t('report.disclaimer')}", ""]
    L += [f"## {t('report.provenance')}", "",
          f"| {t('report.model')} | {t('report.vendor')} | backend | ID | ok | refused | failed |",
          "|---|---|---|---|---:|---:|---:|"]
    for p in syn["provenance"]:
        L.append(f"| {p['model']} | {p['vendor']} | {p['backend']} | {cell(p['model_id'])} | "
                 f"{p['ok']} | {p['refused']} | {p['failed']} |")
    for w in syn["warnings"]:
        if w == "single_vendor":
            L.append(f"\n> ⚠ **{t('run.single_vendor', vendor=syn['provenance'][0]['vendor'])}** "
                     f"{t('run.single_vendor_why')}")
        else:
            L.append(f"\n> ⚠ {t('report.warn.' + w)}")
    L += _verdict_section(t, syn, scope)
    if scope is None:
        v = _consolidated_views(syn)
    else:
        o = syn["jurisdictions"][scope]
        v = {"risks": o["risks"], "unver": o["unverified"], "items": o["items"],
             "headlines": o["headlines"], "unanswered": o["unanswered"],
             "questions": o["counsel_questions"]}
    if v["questions"]:
        L += ["", f"### {t('report.counsel')}", ""] + [f"- {safe(q)}" for q in v["questions"]]
    L += _red_section(t, syn, scope)
    L += ["", f"## {t('report.heatmap')}", ""] + heatmap(t, v["risks"])
    L += ["", f"## {t('report.register')}", ""] + _risk_table(t, v["risks"])
    L += ["", f"## {t('report.checklist')}", "", t("report.checklist_note"), ""]
    L += checklist_lines(t, v["items"], models)
    if v["unanswered"]:
        L += ["", f"### {t('report.unanswered')}", ""]
        L += [f"- {u['item']} ({u['unit']}): {', '.join(u['models'])}" for u in v["unanswered"]]
    if v["headlines"]:
        L += ["", f"## {t('report.headlines')}", ""] + [f"- {safe(h)}" for h in v["headlines"]]
    splits = [r for r in v["risks"] if r["dissent"]]
    if splits:
        L += ["", f"## {t('report.disagreements')}", ""]
        L += [f"- **{r['id']}** ({', '.join(r['supporters'])}) — "
              + "; ".join(f"{d['model']}: {safe(d['evidence'])}" for d in r["dissent"])
              for r in splits]
    if v["unver"]:
        L += ["", f"## {t('report.unverified')}", ""]
        L += [f"- **{r['id']}** {cell(r['anchor'])}: {safe(r['scenario'])} "
              f"({', '.join(r['unverified_claims'])})" for r in v["unver"]]
    if scope is None:
        L += _jmerge_section(t, jm, js)
        if len(js) > 1:
            L += ["", f"### {t('report.per_jurisdiction')}", ""]
            L += [f"- {t('jur.' + j)}: `08-report.v{version}.{j}.md`" for j in js]
    L += _plans_sections(t, run, scope)
    if context:
        L += ["", f"## {t('report.context')}", "",
              f"- {t('report.status')}: {t('context.' + context.get('status', 'skipped'))}"]
        L += [f"- {d['date']} ({t('jur.' + d['jurisdiction'])}): {cell(d['note'])}"
              for d in context.get("sensitive_dates", [])]
        L += [f"- [{cell(f.get('relevance', ''))}] {cell(f.get('date', ''))} "
              f"{cell(f.get('summary', ''))} {source_urls([f])}"
              for f in context.get("findings", [])]
    L += ["", f"## {t('report.ledger')}", "",
          f"| ID | {t('report.location')} | {t('report.claim')} | {t('report.status')} | "
          f"{t('report.sources')} |", "|---|---|---|---|---|"]
    for c in ledger:
        st = c["status"] + (f" ({c['reason']})" if c["status"] == "cannot_verify" else "")
        L.append(f"| {c['id']} | {cell(c['anchor'])} | {cell(c['text'])} ({c['type']}) | {st} | "
                 f"{source_urls(c.get('sources', []))} |")
    if scan.get("flags"):
        fence = "`" * 3
        L += ["", f"## {t('report.injection')}", "", t("report.injection_note"), "", fence + "text"]
        for fl in scan["flags"]:
            L.append(f"{fl['id']} {fl['location']} [{fl['confidence']}] "
                     f"{','.join(fl['categories'])}: {fl['excerpt'][:200]}".replace(fence, "'" * 3))
        L.append(fence)
    if changelog:
        L += ["", f"## {t('report.changelog')}", ""] + [f"- {c}" for c in changelog]
    L += ["", f"<sub>ledger@{snapshot(ledger)}</sub>"]
    return "\n".join(L) + "\n"


def write_report(run: Run, syn: dict, *, lang: str, changelog: list[str] | None = None) -> dict:
    version = latest_version(run) + 1
    js = list(syn["jurisdictions"])
    md = render(run, syn, lang=lang, version=version, changelog=changelog or [])
    scan = read_json(run.path("01-sources/injection-scan.json"), default={"flags": []})
    problems = lint_report(syn, md, [f["excerpt"] for f in scan.get("flags", [])])
    write_text_atomic(run.path(f"08-report.v{version}.md"), md)
    files = [f"08-report.v{version}.md"]
    if len(js) > 1:
        for j in js:
            write_text_atomic(run.path(f"08-report.v{version}.{j}.md"),
                              render(run, syn, lang=lang, version=version,
                                     changelog=changelog or [], scope=j))
            files.append(f"08-report.v{version}.{j}.md")
    ledger = read_ledger(run)
    meta = {"version": version, "files": files, "ledger_snapshot": snapshot(ledger),
            "statuses": {c["id"]: [c["status"], c.get("reason", "")] for c in ledger},
            "verdict": syn["consolidated"]["verdict"],
            "provisional": syn["consolidated"]["provisional"],
            "verdicts": {j: o["verdict"] for j, o in syn["jurisdictions"].items()},
            "red_lines": {j: {k: v["status"] for k, v in o["red_lines"].items()}
                          for j, o in syn["jurisdictions"].items()},
            "risks": len(syn["risks"]), "lint": problems}
    write_json(run.path(f"08-report.v{version}.json"), meta)
    return meta
