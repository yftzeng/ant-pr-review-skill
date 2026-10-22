"""Intake: direction, targets and the context card (replaces the audience layers)."""
from __future__ import annotations

import re
from pathlib import Path

from .i18n import T
from .ui import IO, END_TOKENS, ask_text, checkbox, confirm, dim, prompt, question, radio, section

from .catalog import DEFAULT_JURISDICTIONS, DIRECTIONS, JURISDICTIONS

CHANNELS = ["press_release", "own_social", "kol", "forums", "ads", "media_interview",
            "internal_memo"]
STAKEHOLDERS = ["consumers", "employees", "investors", "regulators", "partners", "competitors",
                "media", "communities"]
CARD_FIELDS = ["org", "parties", "jurisdictions", "channels", "stakeholders", "publish_at",
               "keywords", "embargo"]
URL_RE = re.compile(r"^https?://\S+$", re.I)


def classify_target(s: str) -> dict:
    s = s.strip()
    if URL_RE.match(s):
        return {"kind": "url", "value": s}
    p = Path(s).expanduser()
    if len(s) < 4096 and "\n" not in s and p.exists():
        return {"kind": "path", "value": str(p.resolve())}
    return {"kind": "text", "value": s}


def ask_direction(io: IO, t: T) -> str:
    return radio(io, t, t("intake.direction"),
                 [(d, t(f"intake.direction.{d}")) for d in DIRECTIONS], default="outbound")


def collect_targets(io: IO, t: T) -> list[dict]:
    while True:
        io.say(question(t("intake.targets_help")))
        targets: list[dict] = []
        empty_run = 0
        while True:
            try:
                line = io.ask(prompt("").rstrip() + " ")
            except EOFError:
                break
            s = line.strip()
            if s in END_TOKENS:
                break
            if not s:
                empty_run += 1
                if empty_run >= 2:
                    break
                continue
            empty_run = 0
            tgt = classify_target(s)
            if tgt["kind"] == "text" and targets and targets[-1]["kind"] == "text":
                targets[-1]["value"] += "\n" + s          # same pasted block
                continue
            targets.append(tgt)
            io.say(dim(t(f"intake.ack.{tgt['kind']}", n=len(targets))))
        if targets:
            return targets
        io.say(t("intake.need_target"))



def split_list(text: str) -> list[str]:
    """'A, B、C；D' -> ['A', 'B', 'C', 'D']."""
    return [x.strip() for x in re.split(r"[,，、;；\n]+", text or "") if x.strip()]


def value_label(t: T, field: str, value: str) -> str:
    if value.startswith("custom:"):
        return value[len("custom:"):]
    if field == "jurisdictions":
        return t(f"jur.{value}")
    return t(f"card.{field}.{value}")


def card_line(t: T, field: str, card: dict) -> str:
    v = card.get(field)
    if field == "embargo":
        return t("ui.yes") if v else t("ui.no")
    if isinstance(v, list):
        if not v:
            return t("intake.skipped")
        if field in ("jurisdictions", "channels", "stakeholders"):
            return "、".join(value_label(t, field, x) for x in v)
        return "、".join(v)
    return v or t("intake.skipped")


def _ask_choice_field(io: IO, t: T, field: str, current: list[str]) -> list[str]:
    if field == "jurisdictions":
        opts = [(j, t(f"jur.{j}")) for j in JURISDICTIONS]
        return checkbox(io, t, t("card.jurisdictions"), opts, current or DEFAULT_JURISDICTIONS,
                        min_selected=1)
    base = CHANNELS if field == "channels" else STAKEHOLDERS
    opts = [(o, t(f"card.{field}.{o}")) for o in base]
    opts += [(c, c[len("custom:"):]) for c in current if c.startswith("custom:")]
    return checkbox(io, t, t(f"card.{field}"), opts, current, allow_custom=True)


def ask_field(io: IO, t: T, field: str, card: dict, direction: str) -> None:
    if field in ("jurisdictions", "channels", "stakeholders"):
        card[field] = _ask_choice_field(io, t, field, card.get(field, []))
    elif field in ("parties", "keywords"):
        card[field] = split_list(ask_text(io, t(f"card.{field}")))
    elif field == "embargo":
        card[field] = confirm(io, t, t("card.embargo"),
                              default=card.get("embargo", direction == "outbound"))
    else:
        card[field] = ask_text(io, t(f"card.{field}")).strip()


def ask_card(io: IO, t: T, direction: str, initial: dict | None = None) -> dict:
    card = dict(initial or {})
    if not initial:
        for f in CARD_FIELDS:
            ask_field(io, t, f, card, direction)
    while True:
        io.say(section(t("intake.card")))
        for f in CARD_FIELDS:
            io.say(f"  {t('card.' + f + '.label')}: {card_line(t, f, card)}")
        choices = [("confirm", t("intake.card.confirm"))]
        choices += [(f"edit:{f}", t("intake.card.edit", layer=t("card." + f + ".label")))
                    for f in CARD_FIELDS]
        act = radio(io, t, t("run.resume_choice"), choices, default="confirm")
        if act == "confirm":
            return card
        ask_field(io, t, act.split(":", 1)[1], card, direction)


def parse_choices(values: str | None, allowed: list[str], what: str) -> list[str]:
    out = []
    for item in split_list((values or "").replace("+", ",")):
        if item.startswith("custom:") and item[7:].strip():
            out.append(item)
        elif item in allowed:
            out.append(item)
        else:
            raise ValueError(f"unknown {what} {item!r}; choose from {allowed} or custom:<text>")
    return list(dict.fromkeys(out))


def build_intake_from_args(direction: str, targets: list[str], *, lang: str,
                           jurisdictions: str | None = None, org: str = "",
                           parties: list[str] | None = None, channels: str | None = None,
                           stakeholders: str | None = None, publish_at: str = "",
                           keywords: str | None = None, embargo: bool = False) -> dict:
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {DIRECTIONS}")
    if not targets:
        raise ValueError("at least one --target is needed")
    jur = [j for j in split_list(jurisdictions or "")] or list(DEFAULT_JURISDICTIONS)
    bad = [j for j in jur if j not in JURISDICTIONS]
    if bad:
        raise ValueError(f"unknown jurisdiction(s) {bad}; choose from {JURISDICTIONS}")
    card = {"org": org or "", "parties": [p for x in (parties or []) for p in split_list(x)],
            "jurisdictions": list(dict.fromkeys(jur)),
            "channels": parse_choices(channels, CHANNELS, "channel"),
            "stakeholders": parse_choices(stakeholders, STAKEHOLDERS, "stakeholder"),
            "publish_at": publish_at or "", "keywords": split_list(keywords or ""),
            "embargo": bool(embargo)}
    return {"direction": direction, "targets": [classify_target(x) for x in targets],
            "card": card, "lang": lang}


def run_intake_interactive(io: IO, t: T, lang: str) -> dict:
    direction = ask_direction(io, t)
    targets = collect_targets(io, t)
    card = ask_card(io, t, direction)
    return {"direction": direction, "targets": targets, "card": card, "lang": lang}
