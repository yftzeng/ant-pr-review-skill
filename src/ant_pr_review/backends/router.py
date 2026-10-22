"""Route each roster model to its provider's transport: claude -> `claude -p`,
the rest -> OpenAI-compatible HTTP (D-PR-4)."""
from __future__ import annotations

from .base import Backend, Result


class RouterBackend(Backend):
    name = "auto"

    def __init__(self, transports: dict[str, Backend] | None = None):
        self._t = dict(transports or {})

    def transport(self, provider: str) -> Backend:
        if provider not in self._t:
            if provider == "claude":
                from .claude_cli import ClaudeCliBackend
                self._t[provider] = ClaudeCliBackend()
            else:
                from .openai_compat import OpenAICompatBackend
                self._t[provider] = OpenAICompatBackend(provider)
        return self._t[provider]

    def backend_name(self, model: str) -> str:
        from ..roster import parse
        return self.transport(parse(model)[0]).name

    def run(self, model, *, task, system, prompt, schema, tools=(), effort="high",
            timeout=900) -> Result:
        from ..roster import normalize, parse
        model = normalize(model)
        return self.transport(parse(model)[0]).run(
            model, task=task, system=system, prompt=prompt, schema=schema, tools=tools,
            effort=effort, timeout=timeout)
