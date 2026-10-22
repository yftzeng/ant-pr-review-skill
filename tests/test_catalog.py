import pytest

from ant_pr_review.catalog import (DEFAULT_LENSES, DIMENSIONS, DIRECTIONS, JURISDICTIONS, LENSES,
                                   RED_LINES, checklist, items_for, pack, plan_units,
                                   sensitive_dates_near)


# @S-checklist-001
def test_checklist_is_well_formed():
    items = checklist()
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids)) and len(ids) >= 30
    for i in items:
        assert i["lens"] in LENSES and i["dimension"] in DIMENSIONS
        assert set(i["directions"]) <= set(DIRECTIONS) and i["text"].strip()
        assert i.get("red_line", RED_LINES[0]) in RED_LINES


# @S-checklist-002
def test_every_lens_asks_and_defaults_yield_items():
    for lens in LENSES:
        assert any(i["lens"] == lens for i in checklist()), lens
    for d in DIRECTIONS:
        got = {i["lens"] for i in items_for(d, DEFAULT_LENSES[d])}
        assert got == set(DEFAULT_LENSES[d]), (d, set(DEFAULT_LENSES[d]) - got)


# @S-checklist-003
def test_quick_depth_units():
    units = plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw", "us"], "quick")
    assert [u["id"] for u in units] == ["global.all", "tw.all", "us.all"]


# @S-checklist-004
def test_full_depth_units():
    units = plan_units("outbound", DEFAULT_LENSES["outbound"], ["tw", "us"], "full")
    ids = [u["id"] for u in units]
    assert ids == ["global.journalist", "global.target", "global.internal",
                   "tw.legal", "tw.social", "tw.regulator", "us.legal", "us.social",
                   "us.regulator"]


# @S-checklist-005
@pytest.mark.parametrize("depth", ["quick", "full"])
@pytest.mark.parametrize("direction", DIRECTIONS)
def test_a_unit_never_covers_two_jurisdictions(depth, direction):
    js = list(JURISDICTIONS)
    units = plan_units(direction, list(LENSES), js, depth)
    scoped = {i["id"] for i in checklist() if LENSES[i["lens"]][0] == "j"}
    for u in units:
        assert u["scope"] == "global" or u["scope"] in js
        if u["scope"] == "global":
            assert not scoped & set(u["items"])
        assert u["id"].split(".")[0] == u["scope"]
    for j in js:
        assert any(u["scope"] == j for u in units)


# @S-checklist-006
def test_packs_load_and_are_unverified():
    for j in JURISDICTIONS:
        p = pack(j)
        assert p["code"] == j and p["law"] and p["regulators"] and p["platforms"]
        assert p["verified"] is False
    with pytest.raises(ValueError):
        pack("jp")


# @S-checklist-007
def test_sensitive_dates_without_web():
    got = sensitive_dates_near(["tw"], "2027-02-27") + sensitive_dates_near(["cn"], "2027-06-05")
    notes = [g["note"] for g in got]
    assert "228 Peace Memorial Day" in notes and "Tiananmen anniversary" in notes
    assert sensitive_dates_near(["tw"], "") == [] and sensitive_dates_near(["us"], "2027-03-15") == []
