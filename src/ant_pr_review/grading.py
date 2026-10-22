"""The event assessment (D-0006): a grade from the signals the user ticked, the higher grade
wins and the bottom lines come first; who handles it and whether the kit is activated."""
from __future__ import annotations

from .catalog import ACTIVATION, BOTTOM_LINES, GRADES, OWNERS, SIGNALS

TIER4_BOTTOM = ("injury", "criminal", "minors")  # safety, illegality, minors


def characterised_of(intake: dict) -> bool:
    """Drafting asks it in the brief, an audit on the card; absent reads as not yet."""
    if intake.get("purpose") == "drafting":  # the drafting rule: tier 4 is holding only
        brief = intake.get("brief") or {}
        return bool(brief.get("characterised", False)) and not brief.get("tier4")
    return bool((intake.get("card") or {}).get("characterised", False))


def assess(intake: dict, syn: dict) -> dict:
    card = intake.get("card") or {}
    signals = [s for s in card.get("signals") or [] if s in SIGNALS]
    override = [s for s in signals if s in BOTTOM_LINES]
    if intake.get("purpose") == "drafting":
        override += [f"tier4:{x}" for x in (intake.get("brief") or {}).get("tier4", [])
                     if x in TIER4_BOTTOM]
    confirmed = {k for o in (syn.get("jurisdictions") or {}).values()
                 for k, v in (o.get("red_lines") or {}).items() if v.get("status") == "confirmed"}
    red = [f"red_line:{k}" for k in sorted(confirmed)]
    # An outbound text not yet published, nothing observed: its red line is a publishing
    # block, not an event; the report says what publishing it would make it.
    latent = red if not signals and intake.get("direction") == "outbound" else []
    override += [] if latent else red
    graded = [SIGNALS[s] for s in signals]
    grade = "I" if override else min(graded, key=GRADES.index) if graded else None
    basis = [s for s in signals if SIGNALS[s] == grade and s not in BOTTOM_LINES]
    return {"grade": grade, "owner": OWNERS.get(grade), "basis": basis, "override": override,
            "latent": latent,
            "signals": signals, "activation": ACTIVATION.get(grade, "manual"),
            "characterised": characterised_of(intake)}
