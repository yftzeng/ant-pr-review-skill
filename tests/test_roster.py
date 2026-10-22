import json
import string

import pytest

from ant_pr_review import roster
from ant_pr_review.i18n import LOCALE_DIR, T
from ant_pr_review.onboarding import banner, choose_models, effective_models, first_use
from ant_pr_review.store import PACKAGE_DIR, Config, default_home
from ant_pr_review.ui import ScriptedIO
from conftest import ProbeBackend

OPUS, SONNET, FABLE, GPT = "claude:opus", "claude:sonnet", "claude:fable", "openai:gpt-5"


# @S-roster-001
def test_first_use_preselects_opus_sonnet_and_offers_every_provider(store):
    io = ScriptedIO(["", ""])  # default language, confirm checkbox
    cfg = first_use(io, store, lambda name: ProbeBackend())
    assert cfg.models == [OPUS, SONNET] and store.load_config().models == [OPUS, SONNET]
    assert f"[x] {OPUS}" in io.text and f"[ ] {FABLE}" in io.text
    for p in roster.PROVIDERS:
        assert f"] {p}:" in io.text, p


# @S-roster-002
def test_fewer_than_two_is_refused():
    io = ScriptedIO(["2", "", "4", ""])  # untick sonnet, confirm (refused), tick gpt-5, confirm
    got = choose_models(io, Config(), ProbeBackend())
    assert "at least 2" in io.text and got == [OPUS, GPT]


# @S-roster-003
def test_banner_lists_models_with_vendor_and_command():
    b = banner(T("en"), [OPUS, GPT])
    assert "Reviewers: claude:opus [anthropic], openai:gpt-5 [openai]" in b
    assert "ant-pr-review config models" in b and "one vendor" not in b


# @S-roster-004
def test_config_models_starts_from_saved_choice(store):
    cfg = Config(models=[OPUS, GPT])
    io = ScriptedIO([""])
    choose_models(io, cfg, ProbeBackend())
    store.save_config(cfg)
    assert f"[x] {OPUS}" in io.text and f"[ ] {SONNET}" in io.text and f"[x] {GPT}" in io.text
    assert store.load_config().models == [OPUS, GPT]


# @S-roster-005
def test_failed_probe_is_not_saved():
    io = ScriptedIO(["4", ""])
    got = choose_models(io, Config(), ProbeBackend(down={GPT}))
    assert got == [OPUS, SONNET] and "openai:gpt-5" in io.text and "unavailable" in io.text


# @S-roster-006
def test_strings_follow_language_and_every_key_exists():
    import re
    from pathlib import Path
    assert T("zh-TW")("intake.direction") == "要審查什麼？"
    en = json.loads((LOCALE_DIR / "en.json").read_text())
    for lang in ("zh-TW", "zh-CN"):
        other = json.loads((LOCALE_DIR / f"{lang}.json").read_text())
        assert set(en) == set(other), (lang, set(en) ^ set(other))
        for k, v in en.items():
            fields = {f for _, f, _, _ in string.Formatter().parse(v) if f}
            ofields = {f for _, f, _, _ in string.Formatter().parse(other[k]) if f}
            assert fields == ofields, (lang, k)
    src = Path(roster.__file__).parent
    used = {m.group(1) for f in src.rglob("*.py")
            for m in re.finditer(r"""\bt\(\s*["']([^"'{]+)["']\s*[,)]""", f.read_text())}
    assert used and not used - set(en), used - set(en)
    from ant_pr_review.catalog import DIMENSIONS, JURISDICTIONS, LENSES, RED_LINES
    from ant_pr_review.intake import CARD_FIELDS, CHANNELS, STAKEHOLDERS
    from ant_pr_review.workspace import PHASES
    dynamic = ([f"lens.{x}" for x in LENSES] + [f"dim.{x}" for x in DIMENSIONS]
               + [f"redline.{x}" for x in RED_LINES] + [f"jur.{x}" for x in JURISDICTIONS]
               + [f"phase.{x}" for x in PHASES] + [f"card.{x}.label" for x in CARD_FIELDS]
               + [f"card.channels.{x}" for x in CHANNELS]
               + [f"card.stakeholders.{x}" for x in STAKEHOLDERS]
               + [f"verdict.{x}" for x in ("go", "conditional", "escalate", "no_go")]
               + [f"item.{x}" for x in ("pass", "concern", "fail", "na", "unanswered")]
               + [f"context.{x}" for x in ("done", "skipped", "embargo", "no_search_backend")]
               + [f"report.rl.{x}" for x in ("clear", "advisory", "confirmed", "needs_ruling",
                                             "dismissed")]
               + [f"decide.plan.{x}" for x in ("A", "B", "manual", "hold")])
    assert not set(dynamic) - set(en), set(dynamic) - set(en)


# @S-roster-007
def test_override_does_not_change_saved(store):
    store.save_config(Config(models=[OPUS, SONNET]))
    cfg = store.load_config()
    assert effective_models(cfg, "claude:opus,gemini:gemini-2.5-pro") == [
        OPUS, "gemini:gemini-2.5-pro"]
    assert store.load_config().models == [OPUS, SONNET]
    with pytest.raises(ValueError):
        effective_models(cfg, "claude:opus")


# @N-roster-001
def test_store_never_inside_package(monkeypatch):
    monkeypatch.setenv("ANT_PR_REVIEW_HOME", str(PACKAGE_DIR / "data"))
    with pytest.raises(RuntimeError):
        default_home()


# @S-roster-008
def test_questions_info_warnings_and_phases_are_distinct():
    from ant_pr_review.ui import phase_line, radio, warn
    io = ScriptedIO([""])
    radio(io, T("zh-TW"), "方向：", [("a", "A"), ("b", "B")], default="a")
    assert io.out[0].startswith("\n? 方向：") and io.out[-1].startswith("› ")
    b = banner(T("zh-TW"), [OPUS, GPT])
    first, second = b.split("\n")
    assert first.startswith("ℹ ") and "claude:opus" in first
    assert "ant-pr-review config models" in second
    w = warn("x")
    assert w.startswith("⚠ ")
    line = phase_line(T("zh-TW")("run.phase_start", phase="intake"))
    assert line.startswith("\n━━")
    assert "\x1b[" not in b + io.text + line + w


# @S-roster-009
def test_single_vendor_is_highlighted_never_blocked(tmp_path):
    b = banner(T("en"), [OPUS, SONNET])
    assert "⚠ All reviewers come from one vendor (anthropic)." in b
    assert "miss the same risks" in b
    from ant_pr_review.cli import main
    from ant_pr_review.store import Store
    from ant_pr_review.ui import ScriptedIO as S
    io = S([])
    st = Store(tmp_path / "home")
    rc = main(["new", "--yes", "--backend", "fake", "--models", "claude:opus,claude:sonnet",
               "--target", "# T\n\nHello."], io=io, store=st)
    assert rc == 3 and "one vendor" in io.text
    from ant_pr_review.workspace import list_runs
    run = list_runs(st.runs_dir)[0]
    assert "single_vendor" in json.loads(run.path("06-synthesis.json").read_text())["warnings"]
    assert "All reviewers come from one vendor" in run.path("08-report.v1.md").read_text()


# @S-roster-010
def test_vendors_including_openrouter_paths():
    assert [roster.vendor(m) for m in ("claude:fable", "gemini:gemini-2.5-pro", "grok:grok-4",
                                       "openrouter:anthropic/claude-x")] == [
        "anthropic", "google", "xai", "anthropic"]
    assert roster.single_vendor([OPUS, "openrouter:anthropic/claude-x"]) == "anthropic"
    assert roster.single_vendor([OPUS, GPT]) is None
    assert banner(T("en"), [OPUS, GPT]).count("⚠") == 0


# @S-roster-011
def test_custom_model_from_checkbox():
    io = ScriptedIO(["c", "openrouter:mistralai/mistral-large", ""])
    got = choose_models(io, Config(), ProbeBackend())
    assert got == [OPUS, SONNET, "openrouter:mistralai/mistral-large"]


# @S-roster-012
def test_aliases_normalized_and_bad_models_refused():
    assert effective_models(Config(), "opus,sonnet") == [OPUS, SONNET]
    with pytest.raises(ValueError, match="acme:x"):
        effective_models(Config(), "opus,acme:x")
