# Feature: jurisdiction merge

With two or more jurisdictions, an independent merger call compares the
per-jurisdiction results after all are done; every model that reviewed a
jurisdiction answers that jurisdiction's questions in its own call; the merger
then writes the consolidated view. One consolidated report and one report per
jurisdiction are written. Verdicts stay those computed by code (D-PR-5, D-PR-11).

```gherkin
Feature: jurisdiction merge
  @S-jurisdiction-merge-001
  Scenario: one jurisdiction needs no merger
    Given a synthesis for tw only
    When  the merge phase runs
    Then  no model is called and one report file is written

  @S-jurisdiction-merge-002
  Scenario: the merger compares, each jurisdiction's own reviewers answer, then the merger finalizes
    Given a synthesis for tw and us reviewed by two models
    When  the merge phase runs
    Then  the calls are compare, then one discussion call per (jurisdiction, model) with only that jurisdiction's questions, then final

  @S-jurisdiction-merge-003
  Scenario: a consolidated report and one report per jurisdiction are written
    Given a finished merge for tw and us
    When  the report is written
    Then  08-report.v1.md, 08-report.v1.tw.md and 08-report.v1.us.md exist; the consolidated one holds the comparison and links both

  @S-jurisdiction-merge-004
  Scenario: the merger's text never changes a verdict
    Given a merger whose final answer calls tw "no-go"
    When  the report is written
    Then  the tw verdict is still the one the synthesis computed

  @S-jurisdiction-merge-005
  Scenario: a resumed merge skips the discussion calls already done
    Given a merge where the compare and the tw discussion are done
    When  the merge phase runs again
    Then  only the us discussion and the final call are made
```

## Must NOT
- @N-jurisdiction-merge-001 one model call reviews more than one jurisdiction's scoped lenses

## Revisions
- 2026-10-22 · +S-jurisdiction-merge-001..005 +N-jurisdiction-merge-001 · decision: D-PR-5 -- user: each jurisdiction by its own subagent, then an independent merger that discusses with them
