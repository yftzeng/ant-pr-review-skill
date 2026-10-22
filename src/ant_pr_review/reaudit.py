"""Re-audit of the revision (D-0002): plan A is reviewed again at depth quick by the same
models and jurisdictions, round 1 only, in its own folder so the original reviews are
untouched. No debate and no fact check, so the result is always provisional."""
from __future__ import annotations

import json
import shutil

from .backends.base import Backend
from .catalog import plan_units
from .consensus import synthesize
from .intake import posture_of
from .jsonio import read_json, sha256_bytes, write_json
from .review import load_records, run_round1
from .sources.acquire import run_sources
from .workspace import Run

DIR = "09-plans/reaudit"


def status(run: Run) -> dict:
    return read_json(run.path(f"{DIR}/status.json"), default={"status": "pending"})


def run_reaudit(run: Run, backend: Backend, models: list[str], lang: str,
                thresholds: dict[str, float], *, say=print) -> dict:
    intake = read_json(run.path("00-intake.json"))
    a_path = run.path("09-plans/A.md")
    if intake["direction"] != "outbound" or not a_path.exists():
        return _done(run, {"status": "not_applicable"})
    diff = run.path("09-plans/A.diff")
    if not diff.exists() or not diff.read_text(encoding="utf-8").strip():
        return _done(run, {"status": "unchanged"})
    text = a_path.read_text(encoding="utf-8")
    m = read_json(run.path("03-matrix.json"))
    context = read_json(run.path("02-context.json"), default={"status": "skipped"})
    # Whatever the answers depend on: a change to any of them starts afresh.
    digest = sha256_bytes(json.dumps([text, intake, m, context], ensure_ascii=False,
                                     sort_keys=True).encode("utf-8"))
    sub = Run(run.path(DIR))
    if status(run).get("inputs_sha") != digest and sub.root.exists():
        shutil.rmtree(sub.root)  # another revision: earlier answers do not apply
    sub.root.mkdir(parents=True, exist_ok=True)
    write_json(sub.path("00-intake.json"), dict(intake, targets=[{"kind": "text",
                                                                   "value": text}]))
    if not sub.path("01-sources/segments.json").exists():
        run_sources(sub, crawler=None)
    write_json(sub.path("02-context.json"), context)
    units = plan_units("outbound", m["lenses"], m["jurisdictions"], "quick", posture_of(intake))
    matrix = dict(m, depth="quick", units=units)
    write_json(sub.path("03-matrix.json"), matrix)
    run_round1(sub, backend, models, lang, say=say)
    syn = synthesize(matrix=matrix, reviews=load_records(sub, "04-reviews"), debates={},
                     ledger=[], models=models, thresholds=thresholds)
    syn["consolidated"]["provisional"] = True
    for o in syn["jurisdictions"].values():
        o["provisional"] = True
    write_json(sub.path("06-synthesis.json"), syn)
    ok = any(r.get("status") == "ok" for r in load_records(sub, "04-reviews").values())
    return _done(run, {"status": "done" if ok else "failed", "inputs_sha": digest})


def _done(run: Run, st: dict) -> dict:
    write_json(run.path(f"{DIR}/status.json"), st)
    return st
