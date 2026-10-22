"""Intake: direction, targets and the context card (replaces the audience layers)."""
from __future__ import annotations

import re
from pathlib import Path

from .i18n import T
from .ui import (IO, END_TOKENS, ask_text, checkbox, collect_lines, confirm, dim, prompt, question,
                 radio, section)

from .catalog import (DEFAULT_IDENTITY, DEFAULT_JURISDICTIONS, DEFAULT_POSTURE,
                      DEFAULT_STANDPOINTS, DIRECTIONS, JURISDICTIONS, LEGACY_POSTURES, MEANS,
                      PARTY_TYPES, POSTURES, STANDPOINTS, VALID_IDENTITIES, identity_options)

CHANNELS = ["press_release", "own_social", "kol", "forums", "ads", "media_interview",
            "internal_memo"]
STAKEHOLDERS = PARTY_TYPES  # D-0003: the card's stakeholders use the party types
LEGACY_STAKEHOLDERS = {"consumers": ["victims", "bystanders"], "employees": "staff",
                       "investors": ["private_investors", "public_investors"],
                       "regulators": "regulators", "partners": "partners",
                       "competitors": "competitors", "media": "media",
                       "communities": "community_leaders"}
CARD_FIELDS = ["org", "parties", "jurisdictions", "channels", "stakeholders", "publish_at",
               "keywords", "embargo", "speaker", "background", "locked", "focus"]
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


def ask_posture(io: IO, t: T) -> str:
    return radio(io, t, t("intake.posture"), [(p, t(f"posture.{p}")) for p in POSTURES],
                 default=DEFAULT_POSTURE)


def ask_means(io: IO, t: T) -> list[str]:
    return checkbox(io, t, t("intake.means"), [(m, t(f"means.{m}")) for m in MEANS], MEANS,
                    min_selected=1)


def ask_standpoints(io: IO, t: T) -> list[str]:
    return checkbox(io, t, t("intake.standpoint"), [(s, t(f"standpoint.{s}")) for s in STANDPOINTS],
                    DEFAULT_STANDPOINTS, min_selected=1)


def identity_label(t: T, identity: str) -> str:
    sp, p = identity.split(":", 1)
    return f"{t('standpoint.' + sp + '.short')} - {t('party.' + p)}"


def ask_identities(io: IO, t: T, standpoints: list[str]) -> list[str]:
    opts = [(o, identity_label(t, o)) for o in identity_options(standpoints)]
    return checkbox(io, t, t("intake.identity"), opts,
                    [f"{sp}:organization" for sp in standpoints], min_selected=1)


def check_identities(identities: list[str]) -> list[str]:
    bad = [x for x in identities if ":" not in x
           or x.split(":", 1)[1] not in VALID_IDENTITIES.get(x.split(":", 1)[0], [])]
    if bad:
        raise ValueError(f"not a reasonable identity: {bad}; astroturf is never our role; "
                         f"choose from {identity_options(STANDPOINTS)}")
    return list(dict.fromkeys(identities))


def _valid_identity(x) -> bool:
    if not isinstance(x, str) or x.count(":") != 1:
        return False
    sp, p = x.split(":")
    return p in VALID_IDENTITIES.get(sp, [])


def roles_of(intake: dict) -> dict:
    """Our role as stored, re-validated every time it is read (N-context-card-001): an
    unreasonable or malformed identity, astroturf above all, is dropped and reported;
    nothing left, or an intake written before D-0003, reads as responsible:organization."""
    raw = (intake.get("roles") or {}) if isinstance(intake.get("roles"), dict) else {}
    ids = raw.get("identities")
    ids = [ids] if isinstance(ids, str) else (ids if isinstance(ids, list) else [])
    from .catalog import POLITICAL_IDENTITIES, state_ruled
    js = (intake.get("card") or {}).get("jurisdictions") or []
    organ = any(state_ruled(j) for j in js if isinstance(j, str))

    def ok(x) -> bool:
        return _valid_identity(x) and not (organ and x.split(":")[1] in POLITICAL_IDENTITIES)
    good = list(dict.fromkeys(x for x in ids if ok(x)))
    dropped = [str(x)[:60] for x in ids if not ok(x)]
    good = good or [DEFAULT_IDENTITY]
    return {"standpoints": [s for s in STANDPOINTS if any(i.startswith(s + ":") for i in good)],
            "identities": good, **({"dropped": dropped} if dropped else {})}


def card_stakeholders(card: dict) -> list[str]:
    """The card's stakeholders, with the earlier values mapped onto the party types."""
    return map_stakeholders(card.get("stakeholders", []))


def map_stakeholders(values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        m = LEGACY_STAKEHOLDERS.get(v, v)
        out += m if isinstance(m, list) else [m]
    return list(dict.fromkeys(out))


def posture_of(intake: dict) -> str:
    """An intake written before D-0002 reads as the default posture with every means;
    an earlier posture name maps onto the current one."""
    p = intake.get("posture") or DEFAULT_POSTURE
    return LEGACY_POSTURES.get(p, p)


def means_of(intake: dict) -> list[str]:
    return list(intake.get("means") or MEANS)


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
    if field == "stakeholders":
        return t(f"party.{value}")
    return t(f"card.{field}.{value}")


def card_line(t: T, field: str, card: dict) -> str:
    v = card.get(field)
    if field == "embargo":
        return t("ui.yes") if v else t("ui.no")
    if field == "locked" and v:
        return " / ".join(v)
    if field == "stakeholders":
        v = card_stakeholders(card)
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
    opts = [(o, value_label(t, field, o)) for o in base]
    opts += [(c, c[len("custom:"):]) for c in current if c.startswith("custom:")]
    return checkbox(io, t, t(f"card.{field}"), opts, current, allow_custom=True)


def ask_field(io: IO, t: T, field: str, card: dict, direction: str) -> None:
    if field in ("jurisdictions", "channels", "stakeholders"):
        current = card_stakeholders(card) if field == "stakeholders" else card.get(field, [])
        card[field] = _ask_choice_field(io, t, field, current)
    elif field in ("parties", "keywords"):
        card[field] = split_list(ask_text(io, t(f"card.{field}")))
    elif field == "locked":  # whole sentences, one per line: commas stay inside
        io.say(question(t("card.locked")))
        card[field] = collect_lines(io, t, prompt(""), lambda s: dim("  ✓"))
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
                           keywords: str | None = None, embargo: bool = False,
                           posture: str | None = None, means: str | None = None,
                           speaker: str = "", background: str = "",
                           locked: list[str] | None = None, focus: str = "",
                           roles: list[str] | None = None, tax_id: str = "") -> dict:
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {DIRECTIONS}")
    posture = posture or DEFAULT_POSTURE
    if posture not in POSTURES:
        raise ValueError(f"posture must be one of {POSTURES}")
    chosen = split_list(means or "") or list(MEANS)
    bad_means = [m for m in chosen if m not in MEANS]
    if bad_means:
        raise ValueError(f"unknown means {bad_means}; choose from {MEANS}")
    if not targets:
        raise ValueError("at least one --target is needed")
    jur = [j for j in split_list(jurisdictions or "")] or list(DEFAULT_JURISDICTIONS)
    bad = [j for j in jur if j not in JURISDICTIONS]
    if bad:
        raise ValueError(f"unknown jurisdiction(s) {bad}; choose from {JURISDICTIONS}")
    card = {"org": org or "", "parties": [p for x in (parties or []) for p in split_list(x)],
            "jurisdictions": list(dict.fromkeys(jur)),
            "channels": parse_choices(channels, CHANNELS, "channel"),
            "stakeholders": parse_choices(",".join(map_stakeholders(split_list(stakeholders or ""))),
                                          STAKEHOLDERS, "stakeholder"),
            "publish_at": publish_at or "", "keywords": split_list(keywords or ""),
            "embargo": bool(embargo), "speaker": speaker or "", "background": background or "",
            "locked": [x.strip() for x in (locked or []) if x.strip()], "focus": focus or "",
            **({"tax_id": tax_id.strip()} if tax_id and tax_id.strip() else {})}
    identities = check_identities(roles or [DEFAULT_IDENTITY])
    from .catalog import POLITICAL_IDENTITIES, state_ruled
    organs = [j for j in card["jurisdictions"] if state_ruled(j)]
    if organs and any(i.split(":")[1] in POLITICAL_IDENTITIES for i in identities):
        raise ValueError(f"a party identity is not available with jurisdiction(s) {organs}: "
                         "there the ruling party is a party or state organ, never our role")
    return {"direction": direction,
            "roles": roles_of({"roles": {"identities": identities}}), "posture": posture,
            "means": [m for m in MEANS if m in chosen],
            "targets": [classify_target(x) for x in targets], "card": card, "lang": lang}


def run_intake_interactive(io: IO, t: T, lang: str) -> dict:
    direction = ask_direction(io, t)
    standpoints = ask_standpoints(io, t)
    identities = ask_identities(io, t, standpoints)
    posture = ask_posture(io, t)
    means = ask_means(io, t)
    targets = collect_targets(io, t)
    card = ask_card(io, t, direction)
    return {"direction": direction, "roles": roles_of({"roles": {"identities": identities}}),
            "posture": posture, "means": means, "targets": targets, "card": card, "lang": lang}
