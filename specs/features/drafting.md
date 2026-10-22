# Feature: drafting

The user may ask the tool to write our statement instead of auditing one (purpose
"drafting"; "audit" stays the default). A fixed brief collects the facts (confirmed,
alleged, unknown), the crisis kind, the affected people and their strongest emotion,
the outcome wanted, the decision required, earlier statements, actions and their
status, the approvers and any tier-4 flag; material (internal notes, earlier
statements) may be attached and is read only to check facts. One model writes two
versions that differ in approach under the chosen posture; another model reviews
them against the brief; each version is audited by the same matrix. Code ranks them,
a model writes the reason with the numbers, and the recommended version goes through
the full review, so the report ends with its diff and revised full text. Every claim
is registered as public, internal only, not supportable or needing validation. A gap
stays a `[待查證]` placeholder, and the ready-to-publish file is withheld while any
placeholder or internal note remains.

```gherkin
Feature: drafting
  @S-drafting-001
  Scenario: the purpose is asked first and drafting asks the brief instead of targets
    When  an interactive intake answers Down, Enter at the purpose question
    Then  the purpose is "drafting", the direction is outbound without being asked, the role, posture and means follow, then the brief, the optional material and the card; an Enter at the purpose question keeps "audit" and the flow of an audit is unchanged

  @S-drafting-002
  Scenario: a brief file is validated for a non-interactive run
    Given a brief with confirmed, alleged and unknown facts, a crisis kind, an emotion, a decision and tier-4 flags
    When  it is loaded with --purpose drafting; and when it has no confirmed or alleged fact, an unknown kind, decision or flag, or the direction is inbound
    Then  the first gives facts numbered C1.., A1.., U1.. and the brief is stored in the intake; each of the others is refused with the allowed values named

  @S-drafting-003
  Scenario: an exposé without a confirmed fact stops before anything is sent
    Given the posture expose and a brief whose facts are all alleged or unknown
    When  the draft phase runs
    Then  the run pauses with the reason that an accusation needs a confirmed fact and no model is called

  @S-drafting-004
  Scenario: two versions that differ in approach, a near-duplicate is retried once then dropped
    Given a writer whose two versions share an approach or are at least 80% alike
    When  the draft phase runs
    Then  the writer is asked once more with the reason; still alike, the second version is dropped and the report says so; distinct versions are kept as V1 and V2

  @S-drafting-005
  Scenario: blocking questions are capped at three and asked interactively
    Given a writer that returns five blocking questions
    When  the draft phase runs interactively, and non-interactively
    Then  three are asked and the answers go to the writer once more as user answers; a non-interactive run asks nothing and the report lists the three as open

  @S-drafting-006
  Scenario: tier-4 flags make holding statements and ask for counsel first
    Given a brief with the flag injury
    When  the draft phase runs
    Then  the writer is told to write holding statements only, and the report says counsel and the approvers sign off before anything is published

  @S-drafting-007
  Scenario: the claim register is enforced in code
    Given claims whose basis is a confirmed fact, only an alleged fact, no fact, and a claim marked not supportable or internal only that the text contains
    When  the versions are checked
    Then  the first may stay public; the second and third become needs_validation; a version containing the not-supportable or internal-only claim is disqualified

  @S-drafting-008
  Scenario: placeholders and internal notes are found and block the export
    Given a final text with "[待查證]" and another with "TODO" or "（內部備註）"
    When  the report is written
    Then  each is listed with its place, no ready-to-publish file is written (an earlier one is removed), and the report still is; a claim needing validation, a figure in neither the chosen version nor the brief, the ethics guard's marker, or an escalate or no_go verdict block it too; a clean final text is written as the ready-to-publish file

  @S-drafting-009
  Scenario: the readability checks W1-W8 run in code
    Given a version with an over-long sentence and paragraph, a missing measures part, an officialese phrase, "盡快", a nominalisation, a lead missing "when" and an unsupported superlative
    When  the versions are checked
    Then  W1 to W8 each report the hit; a clean version has none

  @S-drafting-010
  Scenario: each version is audited by the same matrix
    Given a matrix of two units and two models
    When  the draft phase runs
    Then  each version has its own folder with round-1 reviews of the same units and a provisional synthesis, and the original run's reviews are untouched

  @S-drafting-011
  Scenario: the ranking is code and the reason is the model's, with the numbers
    Given V1 go with a pass rate of 80% and V2 conditional, and a reason that cites no number
    When  the versions are ranked
    Then  V1 is recommended for its verdict; a reason that does not name only the recommended version and one of its own figures is replaced by one written in code from the verdict, top score and pass rate; a disqualified version, or one no reviewer answered, is never recommended; when every version is disqualified the run pauses

  @S-drafting-012
  Scenario: another model reviews the drafts against the brief
    Given a roster of two models
    When  the draft phase runs
    Then  the reviewer is not the writer and its findings per version are in the report; a refused or failed review is shown as not reviewed

  @S-drafting-013
  Scenario: the recommended version becomes the text of the full review
    When  the draft phase ends interactively with Enter, and non-interactively
    Then  the recommended version is chosen (interactively another may be picked), its text becomes the run's source, and review, plans and the report follow on it with its diff and revised full text

  @S-drafting-014
  Scenario: the report shows the brief, the versions and the recommendation
    When  the report is written for a drafting run
    Then  it has a drafting section with the brief's counts and decision, each version's approach, verdict, top score, pass-rate bar, placeholders, W-checks and disqualification, the recommendation and its reason, the claim register and the stage review

  @S-drafting-015
  Scenario: examples steer the writer by posture
    Given the examples file
    When  the writer prompt is built for the posture clarify_apologize
    Then  it holds at most six examples of that posture, patterns and counters labelled, each marked unverified, and no example names a person
```

## Must NOT
- @N-drafting-001 a version, a register entry or the ready-to-publish file states an alleged or unknown fact as confirmed, or a ready-to-publish file is written while a placeholder or internal note remains
- @N-drafting-002 the writer is asked for black means, an astroturf voice or text meant to pass as written by someone else (the ethics guard runs on every version)

## Revisions
- 2026-10-22 · created · decision: none -- no feature covers writing new text: every existing feature reviews a given target; drafting adds a brief, versions, a ranking and an export gate
- 2026-10-22 · +S-drafting-001..015, +N-drafting-001..002 the brief, versions, register, checks, ranking and export (user: 固定問答＋可附素材; 2 版，同姿態不同做法; 擋下匯出，報告照樣產生) · decision: D-0005
- 2026-10-22 · ~S-drafting-005,008,011 from the tier-3 review: questions cleaned and guarded; the export also blocked by a claim needing validation, a figure not in the version or brief, an escalate or no_go verdict and the guard's marker; an unaudited version disqualified · decision: D-0005
