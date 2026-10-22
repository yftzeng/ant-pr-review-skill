"""Reviewer roster across vendors (D-PR-4).

A model is named `provider:model`, e.g. `claude:opus`, `openai:gpt-5`,
`openrouter:meta-llama/llama-4-maverick`. A bare Claude alias (`opus`) means
`claude:opus`. The catalog is only a starting list: model names age quickly, and
the probe at setup is the only proof that a model exists.
"""
from __future__ import annotations

import os
import re

PROVIDERS = ["claude", "openai", "gemini", "grok", "openrouter"]

CATALOG = {
    "claude": ["opus", "sonnet", "fable"],
    "openai": ["gpt-5", "gpt-5-mini"],
    "gemini": ["gemini-2.5-pro", "gemini-2.5-flash"],
    "grok": ["grok-4"],
    "openrouter": ["deepseek/deepseek-chat", "meta-llama/llama-4-maverick"],
}

CLAUDE_IDS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "fable": "claude-fable-5-1"}

API_KEYS = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "grok": "XAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY"}

DEFAULT_MODELS = ["claude:opus", "claude:sonnet"]
MIN_REVIEWERS = 2

_SPEC_RE = re.compile(r"^(claude|openai|gemini|grok|openrouter):[A-Za-z0-9._/@:-]{1,120}$")


def normalize(spec: str) -> str:
    s = spec.strip()
    if s in CLAUDE_IDS:
        return f"claude:{s}"
    return s


def parse(spec: str) -> tuple[str, str]:
    s = normalize(spec)
    if not _SPEC_RE.match(s):
        raise ValueError(f"model must look like provider:model with provider in {PROVIDERS}: "
                         f"{spec!r}")
    provider, _, model = s.partition(":")
    return provider, model


def is_valid(spec: str) -> bool:
    try:
        parse(spec)
    except ValueError:
        return False
    return True


def slug(spec: str) -> str:
    """File-safe name for a model, used for per-model record files."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", normalize(spec))


def vendor(spec: str) -> str:
    provider, model = parse(spec)
    if provider == "claude":
        return "anthropic"
    if provider == "openrouter":
        return model.split("/", 1)[0].lower() if "/" in model else "openrouter"
    return {"openai": "openai", "gemini": "google", "grok": "xai"}[provider]


def vendors(models: list[str]) -> list[str]:
    out: list[str] = []
    for m in models:
        v = vendor(m)
        if v not in out:
            out.append(v)
    return out


def single_vendor(models: list[str]) -> str | None:
    """The one vendor when every model comes from it, else None (D-PR-4: warn, never block)."""
    vs = vendors(models)
    return vs[0] if len(vs) == 1 and len(models) >= 1 else None


def has_key(provider: str) -> bool:
    return provider == "claude" or bool(os.environ.get(API_KEYS[provider]))


def catalog_options() -> list[str]:
    return [f"{p}:{m}" for p in PROVIDERS for m in CATALOG[p]]


def can_search(spec: str) -> bool:
    """Web tools with verifiable provenance run only through claude -p (D-PR-12)."""
    return parse(spec)[0] == "claude"
