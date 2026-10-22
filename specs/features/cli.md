# Feature: cli

The `ant-pr-review` command runs a whole review end to end, pauses cleanly
(awaiting a decision, a failed phase, Ctrl-C) and resumes from the first
unfinished phase. Every run prints the active reviewers first.

```gherkin
Feature: cli
  @S-cli-001
  Scenario: a non-interactive review runs to the decision gate
    When  "ant-pr-review new --yes --backend fake --target <text>" runs
    Then  08-report.v1.md and 09-plans/A.md exist, the decision is pending, the exit code is 3
    And   the output names the reviewers and the decide command

  @S-cli-002
  Scenario: resume skips finished phases and continues
    Given a run paused at the decision gate
    When  "decide <run> --yes --choice A" runs, then "resume <run>"
    Then  final.md equals A.md, every phase is done and no model is called again

  @S-cli-003
  Scenario: rerun from review calls the reviewers again and writes a new report
    Given a finished run
    When  "rerun <run> --from review --yes" runs
    Then  every (unit, model) is called again and report v2 is written

  @S-cli-004
  Scenario: an unfinished run is offered when starting interactively
    Given a run paused at the decision gate
    When  "ant-pr-review" starts interactively
    Then  the user is offered to continue that run from phase "decision"

  @S-cli-005
  Scenario: Ctrl-C during a phase leaves it resumable
    Given the backend raises KeyboardInterrupt during review
    When  the run is interrupted
    Then  the review phase is "pending", the exit code is 130 and the resume command is printed

  @S-cli-006
  Scenario: a backend failure pauses the run with a resume hint
    Given every reviewer fails with a backend error
    When  the run reaches review
    Then  the run pauses with exit code 3 and earlier phases stay done

  @S-cli-007
  Scenario: runs lists each run with its direction and next phase
    Given one paused run
    When  "ant-pr-review runs" runs
    Then  the line for that run says "outbound" and "next: decision"

  @S-cli-008
  Scenario: the run folder is named after the target, not its full path
    When  runs start with targets "/tmp/x/my-article.md", "https://example.com/blog/hello-world" and text "# Big News\nBody"
    Then  the folder slugs are "my-article", "example-com-hello-world" and "big-news"

  @S-cli-009
  Scenario: leaving during interactive intake leaves no run folder
    Given no runs
    When  "ant-pr-review" starts interactively and the input ends while the card is asked
    Then  the runs directory has no run in it

  @S-cli-010
  Scenario: an unfinished run can be deleted from the start menu, with confirmation
    Given an unfinished run holding only state.json
    When  the user picks "delete an unfinished run", chooses it, sees its file count and confirms
    Then  the folder is gone; declining the confirmation keeps it

  @S-cli-011
  Scenario: a feed URL lets the user tick articles, and each becomes its own run
    Given a feed with 3 articles
    When  "ant-pr-review" runs interactively with that URL and the user ticks articles 1 and 3
    Then  two runs are created, each holding one article, named after the article titles

  @S-cli-012
  Scenario: non-interactive feeds take the newest N articles
    When  "ant-pr-review new --yes --target <feed> --feed-limit 2" runs
    Then  two runs are created from the first two feed items

  @S-cli-013
  Scenario: a summary table compares every run
    Given two runs with reports and one run without a report
    When  "runs --summary" runs, and again with "--format csv --out summary.csv"
    Then  the table has one row per run with title, direction, verdict, confirmed red lines, risks and next phase
    And   summary.csv holds the same rows with a header line

  @S-cli-014
  Scenario: several jurisdictions in one non-interactive run
    When  "new --yes --backend fake --jurisdictions tw,us --depth full --target <text>" runs
    Then  the matrix has tw and us units, the merge ran, and a consolidated plus two jurisdiction reports exist
```

## Must NOT
- @N-cli-001 a non-interactive run (--yes) waits for keyboard input

## Revisions
- 2026-10-22 · forked from ant-peer-review @3ddd7f5 and rewritten for PR risk review; ids restart in this repo · decision: D-PR-1
