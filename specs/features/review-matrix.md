# Feature: review matrix

Every model answers every unit of the matrix blind (D-PR-3), then
cross-examines the other models inside the same unit. A deterministic
synthesis tallies every checklist item, merges risks into a register, applies
the red-line veto and computes a verdict per jurisdiction; the consolidated
verdict is the worst one (D-PR-6, D-PR-11). Disagreement is reported, never
silently resolved.

```gherkin
Feature: review matrix
  @S-review-matrix-001
  Scenario: every unit and model runs blind and is kept in its own file
    Given units global.all and tw.all and models claude:opus and openai:gpt-5
    When  round 1 runs
    Then  04-reviews/<unit>/<model>.json exists for all four, and no prompt contains another model's answer

  @S-review-matrix-002
  Scenario: a resumed review re-runs only the jobs that failed
    Given round 1 where openai:gpt-5 timed out on tw.all only
    When  the review phase runs again
    Then  only (tw.all, openai:gpt-5) is called

  @S-review-matrix-003
  Scenario: a refusal is recorded and disclosed, not dropped silently
    Given openai:gpt-5 refuses every unit
    When  synthesis runs
    Then  provenance counts its refusals, the tally excludes it, and the report warns about fewer than 2 reviewers

  @S-review-matrix-004
  Scenario: a missing checklist item gets one targeted retry
    Given a model omits LEG-02 in its first answer and answers it on the retry
    When  round 1 runs
    Then  the model was called twice, the retry prompt names LEG-02, and the record has no unanswered item

  @S-review-matrix-005
  Scenario: an item still unanswered after the retry is a gap, not a pass
    Given a model omits LEG-02 twice
    When  synthesis runs
    Then  LEG-02 lists that model as unanswered, the warning "unanswered_items" is raised and the report marks it "∅"

  @S-review-matrix-006
  Scenario: the item verdict is the most severe answer and differing answers are SPLIT
    Given claude:opus answers LEG-01 "pass" and openai:gpt-5 answers "fail"
    When  synthesis runs
    Then  LEG-01 is "fail" with label "SPLIT" and both answers are shown

  @S-review-matrix-007
  Scenario: silence is not agreement
    Given claude:opus raises risk R1 and openai:gpt-5 does not mention it in debate
    When  synthesis runs
    Then  the risk is "SINGLE" with supporters [claude:opus]

  @S-review-matrix-008
  Scenario: corroboration and duplicates merge into consensus
    Given openai:gpt-5 marks its R4 duplicate_of claude:opus R1 and grok:grok-4 corroborates it
    When  synthesis runs
    Then  one risk "CONSENSUS-3" covers both

  @S-review-matrix-009
  Scenario: a dispute makes a risk SPLIT with the dissent recorded
    Given openai:gpt-5 disputes claude:opus R1 with evidence
    When  synthesis runs
    Then  the risk is "SPLIT" and its dissent holds that evidence

  @S-review-matrix-010
  Scenario: a confirmed red line is No-Go whatever the scores
    Given both models flag undisclosed_inauthentic with severity high and every risk scores 1
    When  synthesis runs
    Then  the jurisdiction verdict is "no_go"

  @S-review-matrix-011
  Scenario: a contested red line waits for a human ruling
    Given claude:opus flags election_law and openai:gpt-5 disputes it
    When  synthesis runs
    Then  the red line is "needs_ruling" and the verdict is provisional

  @S-review-matrix-012
  Scenario: an unsupported allegation confirms the fabrication red line
    Given one model flags fabrication_about_party, another disputes it, and the ledger has an unsupported allegation
    When  synthesis runs
    Then  the red line is "confirmed" with that claim as evidence

  @S-review-matrix-013
  Scenario: likelihood and impact are the max over the raisers, with the spread
    Given two models raise the same risk with L 2 and 4, I 3 and 3
    When  synthesis runs
    Then  the risk is 4×3=12 with a likelihood spread of 2 and marked WIDE

  @S-review-matrix-014
  Scenario: the verdict follows the thresholds
    When  the top risk is 16, a legal risk is 12, the top risk is 9, or the top risk is 4
    Then  the verdict is escalate, escalate, conditional, or go

  @S-review-matrix-015
  Scenario: a risk resting on an unverifiable claim is set aside, unless provability is the risk
    Given a backlash risk and a provability risk both resting on a cannot_verify claim
    When  synthesis runs
    Then  the backlash risk is listed as unverified and the provability risk stays in the register

  @S-review-matrix-016
  Scenario: the consolidated verdict is the worst jurisdiction, and global units count everywhere
    Given a global risk scoring 9 and a us.legal risk scoring 16
    When  synthesis runs for tw and us
    Then  tw is conditional, us is escalate, and the consolidated verdict is escalate with us as strictest

  @S-review-matrix-017
  Scenario: material reaches the model only inside the untrusted block
    When  a review prompt is built
    Then  the material sits between the untrusted_content tags and delimiter look-alikes inside it are neutralized

  @S-review-matrix-018
  Scenario: a low-severity red-line flag is advisory and never vetoes
    Given both models flag health_claims with severity low
    When  synthesis runs
    Then  the red line is "advisory" and the verdict is not no_go

  @S-review-matrix-019
  Scenario: cross-examination stays inside its unit
    Given units global.all and tw.all
    When  debate runs
    Then  each debate prompt holds only risks from its own unit, and items whose verdicts differ are listed for answer

  @S-review-matrix-020
  Scenario: an Escalate verdict lists the questions for counsel
    Given a legal risk scoring 12
    When  synthesis runs
    Then  the jurisdiction has a counsel question naming that risk's standard and scenario

  @S-review-matrix-021
  Scenario: the report linter flags abusive, personal, impersonating or decision-making wording
    Given risks whose text says "sloppy", "作者根本不懂", "I am the editor" or "We recommend rejection"
    When  the report is linted
    Then  each risk id is listed and a neutral risk passes

  @S-review-matrix-022
  Scenario: an absence finding must say where the reviewer looked
    Given a risk anchored "absence: whole piece - expected a disclosure" without "checked:"
    When  the report is linted
    Then  the lint lists "absence without checked surfaces"; with "checked: body, footer" it passes

  @S-review-matrix-023
  Scenario: untrusted text cannot inject links, images or HTML into the report
    When  a cell holds "[x](http://evil) ![i](http://e/i.png) <script>"
    Then  the report shows it escaped and inert

  @S-review-matrix-024
  Scenario: the checklist is a checkbox list with a pass-rate bar and every reviewer's verdict
    Given an item answered pass, pass, concern by three models, one answered na, pass by two and left unanswered by one, and one answered na by all
    When  the report is written
    Then  the first reads "- [ ]" with "███████░░░  67%  2/3 ⚠" and each model's mark, the second "- [ ]" with "██████████ 100%  2/2 ✓" and "1 unanswered" (a silent reviewer is never a tick), the third "- [x]" with "n/a"; subtotals per lens and scope and an overall rate follow

  @S-review-matrix-025
  Scenario: the report carries the revision, its re-audit and the timeline
    Given an outbound run with plans and a re-audit done
    When  the report is written
    Then  it holds the A diff, the full revised text, before and after bars per item, the timeline and, with black ticked, the excluded table; the report phase runs after plans, and a missing plan file is skipped, not a crash
  @S-review-matrix-026
  Scenario: a reviewer whose whole unit failed is never a tick
    Given M2's call for global.all failed, so M2 is not among the item's active reviewers
    When  the checklist is rendered for the roster M1, M2
    Then  the item is unticked with "M2 ∅" and "1 unanswered"; an item nobody answered is unticked too
  @S-review-matrix-027
  Scenario: every model answers every party type in a stakeholders unit, and a missing type is a gap
    Given one model answers every party type of tw (the base types plus the pack's political parties) and another leaves out board
    When  the synthesis runs
    Then  the tw matrix has a row per type with both models' answers except board, which lists the second model as unanswered; relevance is the highest and L×I the max; a missing type is retried once; an unknown relevance reads as none

  @S-review-matrix-028
  Scenario: the report shows the stakeholder matrix per jurisdiction, grouped
    When  the report is written
    Then  it has a stakeholder section per jurisdiction with the seven groups, rows sorted by relevance, each type's relevance (∅ when nobody answered), max L×I, and each model's reaction, needs and handling; a type every model rated none is one line; with several jurisdictions the consolidated report keeps only high, L×I ≥ 8 or gap rows; the reaction column is labelled model-simulated
  @S-review-matrix-029
  Scenario: the report has a stress-test section
    When  the report is written for an outbound run
    Then  a stress-test section lists RTM-01..05 and POL-01..03 with their dimension and red-team question once, then per unit the parties tested there (that jurisdiction's parties for the political tests), the pass-rate bar and each model's evidence; the jurisdiction merger sees the panels' POL-03 quotes and names cross-region wording only from them
```

## Must NOT
- @N-review-matrix-001 an unanswered checklist item is counted as a pass
- @N-review-matrix-002 a model call decides a verdict, a label or a red-line status

## Revisions
- 2026-10-22 · forked from ant-peer-review @3ddd7f5 and rewritten for PR risk review; ids restart in this repo · decision: D-PR-1
- 2026-10-22 · +S-review-matrix-024..025 pass-rate bars, revision and timeline in the report · decision: D-0002
- 2026-10-22 · ~S-review-matrix-024 the checklist is a checkbox list with every reviewer's verdict (user: 報告裡的勾選清單) · decision: D-0002
- 2026-10-22 · +S-review-matrix-026, ~S-review-matrix-025 (missing plan files do not stop the report), from the tier-3 review · decision: D-0002
2026-10-22 · +S-review-matrix-027..028 the stakeholder matrix · decision: D-0003
2026-10-22 · ~S-review-matrix-027, 028 from the tier-3 review and the political parties; +S-review-matrix-029 stress tests · decision: D-0003
- 2026-10-22 · ~S-review-matrix-029 second tier-3 review: per-unit parties, question once, merger evidence · decision: D-0003
- 2026-10-22 · ~S-review-matrix-028 reactions labelled model-simulated (borrowed) · decision: D-0003
