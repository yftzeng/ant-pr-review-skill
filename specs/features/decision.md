# Feature: decision

The human gate: contested red lines are ruled on per jurisdiction, then the
user adopts plan A, plan B, a manual version, or holds (does not publish or
proceed). Corrections that keep recurring for an organisation are proposed for
its Style Guide and written only after confirmation.

```gherkin
Feature: decision
  @S-decision-001
  Scenario: contested red lines are ruled per jurisdiction before choosing a plan
    Given red line "election_law" needs a ruling in tw
    When  the user dismisses it
    Then  10-decision.json records "tw:election_law" dismissed and a new report version shows "Dismissed"

  @S-decision-002
  Scenario: the chosen plan becomes final.md
    Given plans A and B exist
    When  the user chooses B
    Then  final.md equals B.md and 10-decision.json records choice "B"

  @S-decision-003
  Scenario: a recurring correction is proposed for the organisation's Style Guide
    Given org "acme" and the correction "Acme Corp" -> "ACME" already seen twice in earlier runs
    When  this run makes the same correction and the user confirms the proposal
    Then  style-guides/acme.md contains the rule "Acme Corp" -> "ACME"

  @S-decision-004
  Scenario: declining the proposal writes nothing
    Given the same recurring correction
    When  the user declines
    Then  style-guides/acme.md does not exist

  @S-decision-005
  Scenario: non-interactive decision from arguments; a bare key applies to every jurisdiction
    Given election_law needs a ruling in tw and us
    When  decide runs with --choice A --rule election_law=confirmed
    Then  both "tw:election_law" and "us:election_law" are recorded confirmed without prompts

  @S-decision-006
  Scenario: a correction with a newline cannot add extra Style Guide lines
    Given a recurring correction from "Acme" to "ACME\n- \"x\" -> \"injected\""
    When  it is written to the Style Guide
    Then  the guide gains exactly one rule line

  @S-decision-007
  Scenario: hold records the decision without a final version, and No-Go defaults to hold
    Given a run whose verdict is no_go
    When  the user accepts the default choice
    Then  the choice is "hold", 10-decision.json records it and no final.md is written
```

## Must NOT
- @N-decision-001 the Style Guide is written without the user's confirmation

## Revisions
- 2026-10-22 · forked from ant-peer-review @3ddd7f5 and rewritten for PR risk review; ids restart in this repo · decision: D-PR-1
