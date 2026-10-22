"""Context scan (D-PR-9): sensitive dates from the packs (no web), then web news about
the named parties and topic, only after the user confirms the queries and never
under embargo. A finding counts only if its URL came back from a tool call."""
from __future__ import annotations

from . import prompts
from .backends.base import Backend, BackendError
from .catalog import sensitive_dates_near
from .factcheck import _provenance_filter
from .schemas import CONTEXT_SEARCH

MAX_QUERIES = 8


def build_queries(card: dict) -> list[str]:
    out = []
    for p in card.get("parties", []):
        out.append(f"{p} latest news controversy")
        out.append(f"{p} lawsuit complaint regulator")
    for kw in card.get("keywords", []):
        out.append(f"{kw} news")
    return list(dict.fromkeys(out))[:MAX_QUERIES]


def base_context(card: dict) -> dict:
    return {"status": "pending", "queries": [], "findings": [], "errors": [],
            "sensitive_dates": sensitive_dates_near(card.get("jurisdictions", []),
                                                    card.get("publish_at", ""))}


def run_queries(backend: Backend, searcher: str, queries: list[str], lang: str, *,
                say=print) -> tuple[list[dict], list[str]]:
    findings, errors = [], []
    for q in queries:
        say(f"  … {q}")
        try:
            res = backend.run(searcher, task="context", system=prompts.context_system(lang),
                              prompt=prompts.context_prompt(q), schema=CONTEXT_SEARCH,
                              tools=("WebSearch",), effort="medium")
        except BackendError as e:
            errors.append(f"{q}: {e.reason}")
            continue
        if res.refused or not res.data:
            errors.append(f"{q}: refused")
            continue
        kept = _provenance_filter(res.data.get("findings", []), res.tool_results)
        dropped = len(res.data.get("findings", [])) - len(kept)
        if dropped:
            errors.append(f"{q}: {dropped} finding(s) without a searched source dropped")
        findings += [dict(f, query=q) for f in kept]
    return findings, errors
