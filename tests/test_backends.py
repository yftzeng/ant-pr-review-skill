import json

import pytest

from ant_pr_review.backends.base import Backend, BackendError, Result
from ant_pr_review.backends.openai_compat import OpenAICompatBackend
from ant_pr_review.backends.router import RouterBackend
from ant_pr_review.schemas import obj

SCHEMA = obj({"ok": {"type": "boolean"}})


class Rec(Backend):
    def __init__(self, name):
        self.name, self.calls = name, []

    def run(self, model, **kw):
        self.calls.append(model)
        return Result(model=model, model_id=model, data={"ok": True})


def answer(content=None, refusal=None):
    return {"choices": [{"message": {"content": content, "refusal": refusal},
                         "finish_reason": "stop"}]}


class Post:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, url, key, body, timeout):
        self.calls.append({"url": url, "key": key, "body": body})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


# @S-backends-001
def test_router_sends_each_model_to_its_transport():
    t = {p: Rec(p) for p in ("claude", "openai", "openrouter")}
    r = RouterBackend(t)
    for m in ("opus", "openai:gpt-5", "openrouter:deepseek/deepseek-chat"):
        r.run(m, task="x", system="", prompt="", schema=SCHEMA)
    assert t["claude"].calls == ["claude:opus"]
    assert t["openai"].calls == ["openai:gpt-5"]
    assert t["openrouter"].calls == ["openrouter:deepseek/deepseek-chat"]


# @S-backends-002
def test_openai_call_has_key_model_and_schema(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANT_PR_REVIEW_OPENAI_BASE_URL", "https://proxy.example/v1/")
    post = Post(answer(json.dumps({"ok": True})))
    res = OpenAICompatBackend("openai", post=post).run(
        "openai:gpt-5", task="review", system="sys", prompt="p", schema=SCHEMA)
    c = post.calls[0]
    assert c["url"] == "https://proxy.example/v1/chat/completions" and c["key"] == "sk-test"
    assert c["body"]["model"] == "gpt-5"
    assert c["body"]["response_format"]["type"] == "json_schema"
    assert c["body"]["response_format"]["json_schema"]["schema"] == SCHEMA
    assert res.data == {"ok": True} and res.model_id == "gpt-5"


# @S-backends-003
def test_json_schema_rejected_falls_back_to_json_object(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    post = Post(BackendError("HTTP 400: response_format json_schema not supported"),
                answer("```json\n{\"ok\": false}\n```"))
    res = OpenAICompatBackend("gemini", post=post).run(
        "gemini:gemini-2.5-pro", task="x", system="s", prompt="p", schema=SCHEMA)
    second = post.calls[1]["body"]
    assert second["response_format"] == {"type": "json_object"}
    assert '"ok"' in second["messages"][1]["content"] and res.data == {"ok": False}


# @S-backends-004
def test_invalid_output_retried_then_reported(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "k")
    post = Post(answer(json.dumps({"ok": "yes"})), answer("not json"))
    with pytest.raises(BackendError) as e:
        OpenAICompatBackend("grok", post=post).run("grok:grok-4", task="x", system="s",
                                                   prompt="p", schema=SCHEMA)
    assert e.value.reason == "invalid_output" and len(post.calls) == 2


# @S-backends-005
def test_missing_key_or_tools_fail_clearly(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    b = OpenAICompatBackend("openai", post=Post())
    with pytest.raises(BackendError, match="OPENAI_API_KEY"):
        b.run("openai:gpt-5", task="x", system="s", prompt="p", schema=SCHEMA)
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    with pytest.raises(BackendError) as e:
        b.run("openai:gpt-5", task="x", system="s", prompt="p", schema=SCHEMA,
              tools=("WebSearch",))
    assert e.value.reason == "no_search_backend"


# @S-backends-006
def test_refusal_is_recorded(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    post = Post(answer(None, refusal="I can't help with that"))
    res = OpenAICompatBackend("openrouter", post=post).run(
        "openrouter:x/y", task="x", system="s", prompt="p", schema=SCHEMA)
    assert res.refused and res.data is None and "can't help" in res.refusal_detail


# @N-backends-001
def test_no_runtime_dependencies():
    import tomllib
    from pathlib import Path
    py = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert py["project"]["dependencies"] == []
