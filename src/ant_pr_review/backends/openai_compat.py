"""OpenAI-compatible chat/completions over stdlib HTTP: OpenAI, Gemini, Grok, OpenRouter.

No runtime dependencies (the deps gate refuses them). Structured output is asked
for with response_format json_schema; a provider that rejects it gets json_object
with the schema in the prompt. Output is always validated here, with one retry.
Web tools are not offered (D-PR-12).
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request

from ..schemas import validate
from .base import Backend, BackendError, Result

BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "grok": "https://api.x.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
MAX_ATTEMPTS = 2


def base_url(provider: str) -> str:
    return (os.environ.get(f"ANT_PR_REVIEW_{provider.upper()}_BASE_URL")
            or BASE_URLS[provider]).rstrip("/")


def _post(url: str, key: str, body: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise BackendError(f"HTTP {e.code}: {detail}",
                           reason="error" if e.code != 408 else "timeout") from e
    except (TimeoutError, socket.timeout) as e:
        raise BackendError(f"timed out after {timeout}s", reason="timeout") from e
    except urllib.error.URLError as e:
        raise BackendError(f"network: {e.reason}", reason="offline") from e


class OpenAICompatBackend(Backend):
    def __init__(self, provider: str, *, post=None):
        from ..roster import API_KEYS
        self.provider = provider
        self.name = f"{provider}-api"
        self.key_env = API_KEYS[provider]
        self._post = post or _post
        self.json_schema_ok = True  # flips to False after a provider rejects it

    def body(self, model_id: str, system: str, prompt: str, schema: dict) -> dict:
        msgs = [{"role": "system", "content": system}]
        if self.json_schema_ok:
            fmt = {"type": "json_schema",
                   "json_schema": {"name": "answer", "schema": schema, "strict": True}}
            msgs.append({"role": "user", "content": prompt})
        else:
            fmt = {"type": "json_object"}
            msgs.append({"role": "user", "content": prompt + "\n\nAnswer with one JSON object "
                         "that validates against this JSON Schema:\n"
                         + json.dumps(schema, ensure_ascii=False)})
        return {"model": model_id, "messages": msgs, "response_format": fmt}

    def run(self, model, *, task, system, prompt, schema, tools=(), effort="high",
            timeout=900) -> Result:
        from ..roster import parse
        provider, model_id = parse(model)
        if tools:
            raise BackendError(f"{model}: web tools are only available through claude "
                               "(D-PR-12)", reason="no_search_backend")
        key = os.environ.get(self.key_env)
        if not key:
            raise BackendError(f"{model}: set {self.key_env}", reason="error")
        url = base_url(provider) + "/chat/completions"
        last = ""
        for _ in range(MAX_ATTEMPTS):
            try:
                resp = self._post(url, key, self.body(model_id, system, prompt, schema), timeout)
            except BackendError as e:
                if self.json_schema_ok and "response_format" in str(e):
                    self.json_schema_ok = False
                    continue
                raise
            choice = (resp.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            if msg.get("refusal") or choice.get("finish_reason") == "content_filter":
                return Result(model=model, model_id=model_id, data=None, refused=True,
                              refusal_detail=str(msg.get("refusal") or "content_filter")[:300],
                              raw=resp)
            text = msg.get("content") or ""
            try:
                data = json.loads(_strip_fence(text))
            except json.JSONDecodeError:
                last = "not JSON: " + text[:200]
                continue
            errs = validate(data, schema)
            if not errs:
                return Result(model=model, model_id=model_id, data=data, raw=resp)
            last = "; ".join(errs[:5])
        raise BackendError(f"{model}: no valid output after {MAX_ATTEMPTS} attempts: {last}",
                           reason="invalid_output")


def _strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()
