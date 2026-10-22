"""First-use setup and `config` subcommands: language and the reviewer roster."""
from __future__ import annotations

from . import roster
from .backends.base import Backend
from .i18n import T
from .store import LANGS, Config, Store
from .ui import IO, checkbox, dim, info, radio, warn

LANG_LABELS = {"en": "English", "zh-TW": "繁體中文", "zh-CN": "简体中文"}


def choose_lang(io: IO, cfg: Config) -> None:
    t = T(cfg.lang)
    cfg.lang = radio(io, t, t("setup.lang"), [(k, LANG_LABELS[k]) for k in LANGS],
                     default=cfg.lang) or cfg.lang


def model_label(t: T, spec: str) -> str:
    provider = roster.parse(spec)[0]
    tag = "" if roster.has_key(provider) else "  " + t("setup.no_key",
                                                         env=roster.API_KEYS[provider])
    return f"{spec}  [{roster.vendor(spec)}]{tag}"


def choose_models(io: IO, cfg: Config, backend: Backend | None) -> list[str]:
    """Checkbox over every provider's catalog (arrow keys; 'c' adds provider:model).
    Each pick is probed; a model that fails is not saved."""
    t = T(cfg.lang)
    while True:
        specs = roster.catalog_options()
        specs += [m for m in cfg.models if m not in specs]
        picked = checkbox(io, t, t("setup.models"), [(m, model_label(t, m)) for m in specs],
                          cfg.models, min_selected=roster.MIN_REVIEWERS, allow_custom=True)
        ok = []
        for raw in picked:
            m = roster.normalize(raw[len("custom:"):] if raw.startswith("custom:") else raw)
            if not roster.is_valid(m):
                io.say(t("setup.model_bad", model=m))
                continue
            err = backend.probe(m) if backend else None
            if err:
                io.say(t("setup.model_unavailable", model=m, reason=err[:200]))
            else:
                ok.append(m)
        if len(ok) >= roster.MIN_REVIEWERS:
            cfg.models = ok
            sv = vendor_warning(t, ok)
            if sv:
                io.say(sv)
            return ok
        io.say(t("ui.min_selected", n=roster.MIN_REVIEWERS))


def first_use(io: IO, store: Store, backend_factory) -> Config:
    cfg = store.load_config()
    if cfg.configured:
        return cfg
    io.say(T(cfg.lang)("setup.welcome"))
    choose_lang(io, cfg)
    choose_models(io, cfg, backend_factory(cfg.backend))
    store.save_config(cfg)
    io.say(T(cfg.lang)("setup.saved", path=str(store.config_path)))
    cfg.configured = True
    return cfg


def vendor_warning(t: T, models: list[str]) -> str | None:
    """Highlighted, never blocking (D-PR-4)."""
    v = roster.single_vendor(models)
    if not v:
        return None
    return warn(t("run.single_vendor", vendor=v)) + "\n" + dim("  " + t("run.single_vendor_why"))


def banner(t: T, models: list[str]) -> str:
    """The active reviewers with their vendors, the change hint, and the vendor warning."""
    names = ", ".join(f"{m} [{roster.vendor(m)}]" for m in models)
    out = info(t("run.banner", models=names)) + "\n" + dim("  " + t("run.banner_hint"))
    sv = vendor_warning(t, models)
    return out + ("\n" + sv if sv else "")


def parse_models_override(value: str) -> list[str]:
    models = [roster.normalize(m) for m in value.split(",") if m.strip()]
    bad = [m for m in models if not roster.is_valid(m)]
    if bad:
        raise ValueError(f"unknown model(s): {', '.join(bad)}; use provider:model with provider "
                         f"in {roster.PROVIDERS}")
    if len(models) < roster.MIN_REVIEWERS:
        raise ValueError(f"at least {roster.MIN_REVIEWERS} reviewers are needed")
    return list(dict.fromkeys(models))


def effective_models(cfg: Config, override: str | None) -> list[str]:
    """The roster for this run: a --models override wins but is never saved."""
    return parse_models_override(override) if override else list(cfg.models)
