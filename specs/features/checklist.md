# Feature: checklist

A fixed risk checklist (`checklists/default.toml`), lenses, red lines and
jurisdiction packs (`jurisdictions/*.toml`) define what is asked. The review
matrix is built from them: units of (lens group, scope), where a
jurisdiction-scoped lens gets one unit per jurisdiction (D-PR-2, D-PR-5).

```gherkin
Feature: checklist
  @S-checklist-001
  Scenario: every checklist item is well formed
    When  the checklist loads
    Then  ids are unique and every item has a known lens, dimension, direction and red line (if any)

  @S-checklist-002
  Scenario: every lens asks something, and every direction's default lenses yield items
    When  items are listed per lens and per direction
    Then  no lens is empty and each direction's default lenses give items for every one of those lenses that applies

  @S-checklist-003
  Scenario: quick depth is one global unit plus one unit per jurisdiction
    When  the outbound matrix is planned for tw and us at depth quick
    Then  the units are "global.all", "tw.all" and "us.all"

  @S-checklist-004
  Scenario: full depth is one unit per lens, per jurisdiction for scoped lenses
    When  the outbound matrix is planned for tw and us at depth full
    Then  there is one global unit per global lens and one unit per scoped lens and jurisdiction, 9 in all

  @S-checklist-005
  Scenario: a jurisdiction unit never covers two jurisdictions
    When  any matrix is planned for several jurisdictions
    Then  every unit's scope is "global" or exactly one jurisdiction, and scoped items appear only in jurisdiction units

  @S-checklist-006
  Scenario: the four jurisdiction packs load and say they are unverified
    When  the packs tw, us, eu and cn load
    Then  each has laws, regulators and platforms and verified = false; an unknown code is refused

  @S-checklist-007
  Scenario: sensitive dates near the publish date are found without the web
    When  the publish date is 2027-02-27 for tw and 2027-06-05 for cn
    Then  228 Peace Memorial Day and the June 4 anniversary are reported
```

## Revisions
- 2026-10-22 · forked from ant-peer-review @3ddd7f5 and rewritten for PR risk review; ids restart in this repo · decision: D-PR-1
