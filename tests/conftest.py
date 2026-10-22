import pytest

from ant_pr_review.backends.base import Backend, BackendError, Result
from ant_pr_review.store import Store


class ProbeBackend(Backend):
    """Answers probes; models in `down` fail."""
    name = "probe"

    def __init__(self, down=()):
        self.down = set(down)

    def run(self, model, *, task, system, prompt, schema, tools=(), effort="high", timeout=900):
        if model in self.down:
            raise BackendError("model not available on this plan")
        return Result(model=model, model_id=model, data={"ok": True})


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "home")


@pytest.fixture(autouse=True)
def _no_politeness_delay(monkeypatch):
    """Tests talk to local servers; the 1 s per-host politeness pause only slows them."""
    import ant_pr_review.sources.crawler as crawler
    if hasattr(crawler, "DEFAULT_MIN_INTERVAL"):
        monkeypatch.setattr(crawler, "DEFAULT_MIN_INTERVAL", 0.0)
