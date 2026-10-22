import pytest

from ant_pr_review.i18n import T
from ant_pr_review.intake import ask_card, build_intake_from_args, collect_targets
from ant_pr_review.ui import ScriptedIO

t = T("en")
# org, parties, jurisdictions, channels, stakeholders, publish_at, keywords, embargo,
# speaker, background, locked (lines, then /done), focus
FILL = ["Acme", "Beta Corp、Gamma", "", "1", "", "", "2027-01-05", "phones", "", "", "", "/done", "", "", ""]  # ... signals, characterised


# @S-context-card-001
def test_targets_classified_and_echoed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notes").mkdir()
    io = ScriptedIO(["https://example.com/a", "notes", "Some pasted text", "/done"])
    got = collect_targets(io, t)
    assert [x["kind"] for x in got] == ["url", "path", "text"]
    assert got[1]["value"] == str(tmp_path / "notes")
    assert "#1" in io.text and "#2" in io.text and "#3" in io.text


# @S-context-card-002
def test_two_empty_lines_or_eof_end():
    assert len(collect_targets(ScriptedIO(["https://example.com/a", "", ""]), t)) == 1
    assert len(collect_targets(ScriptedIO(["https://example.com/a"]), t)) == 1


# @S-context-card-003
def test_consecutive_text_lines_merge():
    got = collect_targets(ScriptedIO(["Line one", "Line two", "Line three", "/done"]), t)
    assert got == [{"kind": "text", "value": "Line one\nLine two\nLine three"}]


# @S-context-card-004
def test_empty_list_asks_again():
    io = ScriptedIO(["/done", "https://example.com/a", "/done"])
    got = collect_targets(io, t)
    assert "at least one target" in io.text
    assert got == [{"kind": "url", "value": "https://example.com/a"}]


# @S-context-card-005
def test_jurisdictions_checkbox_default_taiwan_min_one():
    card = ask_card(ScriptedIO(FILL + [""]), t, "outbound")
    assert card["jurisdictions"] == ["tw"]
    io = ScriptedIO(FILL[:2] + ["2 3", ""] + FILL[3:] + [""])
    assert ask_card(io, t, "outbound")["jurisdictions"] == ["tw", "us", "eu"]
    io = ScriptedIO(FILL[:2] + ["1", "", "4", ""] + FILL[3:] + [""])
    card = ask_card(io, t, "outbound")
    assert "Choose at least 1" in io.text and card["jurisdictions"] == ["cn"]


# @S-context-card-006
def test_card_edit_before_confirm():
    io = ScriptedIO(FILL + ["3", "Delta", ""])  # edit parties (3rd option), then confirm
    card = ask_card(io, t, "outbound")
    assert card["parties"] == ["Delta"]
    assert card["org"] == "Acme" and card["channels"] == ["press_release"]
    assert card["publish_at"] == "2027-01-05" and card["keywords"] == ["phones"]


# @S-context-card-007
def test_non_interactive_intake_from_args():
    it = build_intake_from_args("operation", ["text"], lang="en", jurisdictions="tw,cn",
                                parties=["A, B"], channels="kol,forums", embargo=True)
    assert it["direction"] == "operation"
    c = it["card"]
    assert c["jurisdictions"] == ["tw", "cn"] and c["parties"] == ["A", "B"]
    assert c["channels"] == ["kol", "forums"] and c["embargo"] is True
    assert build_intake_from_args("outbound", ["x"], lang="en")["card"]["jurisdictions"] == ["tw"]


# @S-context-card-008
@pytest.mark.parametrize("kw,needle", [({"jurisdictions": "jp"}, "jurisdiction"),
                                       ({"channels": "tv"}, "channel")])
def test_unknown_values_refused(kw, needle):
    with pytest.raises(ValueError, match=needle):
        build_intake_from_args("outbound", ["x"], lang="en", **kw)
    with pytest.raises(ValueError, match="direction"):
        build_intake_from_args("sideways", ["x"], lang="en")


# @S-context-card-009
def test_embargo_default_depends_on_direction():
    assert ask_card(ScriptedIO(FILL + [""]), t, "outbound")["embargo"] is True
    assert ask_card(ScriptedIO(FILL + [""]), t, "inbound")["embargo"] is False
