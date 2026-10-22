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
    Then  there is one global unit per global lens and one unit per scoped lens and jurisdiction, 11 in all

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
    Then  228 Peace Memorial Day and the June 4 anniversary are reported; a date with a year (the 2026 local elections) is reported only in that year

  @S-checklist-008
  Scenario: posture items are asked only under their posture
    When  the outbound quick matrix is planned under clarify_apologize, and under expose
    Then  under clarify_apologize it holds CLR-01, CLR-02, APO-01 and APO-02 and no PRO, EXP or RBT item; under expose it holds EXP-01, EXP-02 and EXP-03 and no CLR or APO item

  @S-checklist-009
  Scenario: every posture is asked about in every direction
    When  the matrix is planned for each direction with its default lenses under each posture
    Then  each has at least one item of that posture, and an unknown posture in the checklist or the planner is refused
  @S-checklist-010
  Scenario: the ticked means never narrow the review
    Given an intake whose ticked means are only white
    When  the review prompt is built
    Then  it asks every item from the white, gray and black angles and does not name the ticked means; only the timeline prompt does
  @S-checklist-011
  Scenario: the stakeholders lens asks one item per group in every jurisdiction
    When  any direction's default matrix is planned for tw and us at quick and full depth
    Then  STK-01..07 are asked in the tw and us units and never in a global unit

  @S-checklist-012
  Scenario: role items are asked only for a matching identity
    When  the matrix is planned for identities [responsible:board] and for [related:short_activists]
    Then  the first holds ROL-01 and no ROL-04; the second holds ROL-04 and no ROL-01; an item for an unknown party type is refused

  @S-checklist-013
  Scenario: the borrowed items are in the checklist and credited
    When  the checklist loads
    Then  JOU-06..09, SOC-07, SOC-08, INT-04, RSP-04, APO-03 and EXP-04 exist with their source in docs/REFERENCES.md
  @S-checklist-014
  Scenario: the role stress tests and the political stress tests are asked per jurisdiction
    When  the outbound and inbound matrices are planned for tw and cn
    Then  RTM-01..05 and POL-01..03 are in the tw and cn units, not in global units, and not in an operation matrix
  @S-checklist-015
  Scenario: the second set of borrowed items is in the checklist and credited
    When  the checklist loads
    Then  JOU-10, JOU-11, INT-05, REG-05, RSP-05 and SOC-09 exist, JOU-06 names early scapegoats and "it will not happen again", and each source is in docs/REFERENCES.md with its commit
  @S-checklist-016
  Scenario: the wepr borrowed items are in the checklist and credited
    When  the checklist loads
    Then  LEG-11, REG-06, JOU-12, SOC-10, INT-06 and THR-05 exist; LEG-02, RSP-01, JOU-10 and INT-03 carry the amendments; each source is in docs/REFERENCES.md with its commit
  @S-checklist-017
  Scenario: the news and crisis borrowed items are in the checklist, packs and parties
    When  the checklist, the tw and cn packs and the parties load
    Then  EXP-05, LEG-12, LEG-13, JOU-13, JOU-14, POL-04, INT-07, RSP-06 and SOC-11 exist; tw lists the Anti-Infiltration Act, the Political Donations Act, Constitution art. 73 and Code of Criminal Procedure art. 245 and a 2026 poll blackout; cn lists Maimai; the channel party names franchisees; each source is in docs/REFERENCES.md
  @S-checklist-018
  Scenario: the items from the user's own notes are in the checklist
    When  the checklist loads
    Then  JOU-15 (answer the question asked), LEG-14 (no exoneration overclaim) and INT-08 (no blame on named staff) exist, and APO-01, SOC-10, JOU-06, SOC-07 and LEG-03 carry the amendments
  @S-checklist-019
  Scenario: the items from the brake-pedal commentary videos are in the checklist and credited
    When  the checklist loads
    Then  JOU-16 (a denial with an unexplained fix), JOU-17 (evidence others can check; fast actions, slow conclusions) and JOU-18 (one voice and an agreed split across a shared brand; who commissioned a cited test) exist, JOU-09 names when a defensive or compliance answer fits and STK-01 holds executives to the approved line off the record; the videos are credited in docs/REFERENCES.md by title and id, with no person named
```

## Revisions
- 2026-10-22 · forked from ant-peer-review @3ddd7f5 and rewritten for PR risk review; ids restart in this repo · decision: D-PR-1
- 2026-10-22 · +S-checklist-008..009 posture items (CLR, APO, ATK, DEF) · decision: D-0002
- 2026-10-22 · +S-checklist-010 means shape only the report's means, never the checklist (user: 不會影響檢查項，只會影響最後報告的手段) · decision: D-0002
- 2026-10-22 · ~S-checklist-008 posture items CLR+APO (clarify_apologize), PRO (promote), EXP (expose), RBT (rebut) · decision: D-0002
2026-10-22 · +S-checklist-011..013 stakeholders lens, role items, borrowed items · decision: D-0003
- 2026-10-22 · ~S-checklist-004 11 units with the stakeholders lens · decision: D-0003
2026-10-22 · ~S-checklist-011 STK-07 politics; +S-checklist-014 role and political stress tests (user: 角色壓力測試檢核矩陣, Political Red-Teaming) · decision: D-0003
- 2026-10-22 · ~S-checklist-007 dated sensitive dates (elections) · decision: D-0003
- 2026-10-22 · +S-checklist-015 borrowed items from five more repos (user: 現在併進去) · decision: D-0003
- 2026-10-22 · +S-checklist-016 items borrowed from wepr-growth-skills (user: 現在併進去) · decision: D-0003
- 2026-10-22 · +S-checklist-017 items from med-political, med-news-reporter, ziyu, crisis-pr-response (user: 現在併進去) · decision: D-0003
- 2026-10-22 · +S-checklist-018 items from the user's own reference notes (user: 讀過並整理借鏡，不收進 repo) · decision: D-0003
- 2026-10-22 · +S-checklist-019 items from three brake-pedal crisis commentary videos (user: 按你建議) · decision: D-0003
