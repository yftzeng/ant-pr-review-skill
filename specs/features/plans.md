# Feature: plans

After the report, plans are written by one model and re-reviewed by another
(from another vendor when the roster has one): outbound gets A (smallest safe
edit, character-level diff), B (lawful alternative) and C (response kit);
operation gets B as "do not proceed" or a transparent alternative, plus C;
inbound gets B as response options, plus C. Every plan passes the ethics guard
(D-PR-7): one retry with the guard's feedback, then the offending text is
removed with a visible marker and recorded.

```gherkin
Feature: plans
  @S-plans-001
  Scenario: the A diff marks changes character by character
    Given a CJK paragraph where one character changes
    When  the A diff is written
    Then  the inline line marks only that character

  @S-plans-002
  Scenario: each direction gets its own plans
    When  plans run for outbound, operation and inbound
    Then  outbound writes A, B and C; operation writes B (operation schema) and C, no A; inbound writes B (response options) and C

  @S-plans-003
  Scenario: plans are re-reviewed by a model from another vendor when there is one
    Given the roster claude:opus, claude:sonnet, openai:gpt-5
    When  plans run
    Then  claude:opus writes and openai:gpt-5 re-reviews A and B

  @S-plans-004
  Scenario: unknown paragraph ids from a model are ignored and reported
    When  a plan returns paragraph id D9.P99
    Then  the text is unchanged there and a warning names the id

  @S-plans-005
  Scenario: sentence ids and inserted paragraphs from a model are applied
    When  a plan replaces D1.P02.S1 and inserts D1.P02+
    Then  only that sentence changes and the new paragraph follows D1.P02

  @S-plans-006
  Scenario: evasion advice is sent back once and fixed on the retry
    Given plan C first suggests posting "from alt accounts so it cannot be traced to us", then a clean kit
    When  plans run
    Then  the retry prompt names the hit, the final kit is clean and ethics.json records first hits and no redaction

  @S-plans-007
  Scenario: what is left after the retry is removed and marked
    Given plan B keeps proposing sockpuppet comments
    When  plans run
    Then  B.md holds "[removed by ethics guard: persona]" instead of that text and ethics.json records redacted

  @S-plans-008
  Scenario: an unsupported allegation kept verbatim is laundering and is removed
    Given the ledger marks the allegation at D1.P02.S1 unsupported and plan A leaves that sentence in place
    When  plans run
    Then  A.md no longer holds that sentence and shows the laundering marker with the claim id

  @S-plans-009
  Scenario: advice against a practice is not a hit
    When  the guard reads "Never use sockpuppets or fake accounts" and "不要使用人頭帳號"
    Then  it finds nothing
    But   "No one will know these are fake accounts", "Avoid detection by using alt accounts" and "Don't hesitate to use sockpuppets" are hits

  @S-plans-010
  Scenario: the operation plan B has no field for an improved operation
    When  the operation plan-B schema is read
    Then  its recommendation is only do_not_proceed or transparent_alternative and it has no field for a revised operation plan

  @S-plans-011
  Scenario: the report redacts evasion advice in a reviewer's mitigation and lints it
    Given a risk whose mitigation says to "rotate IP addresses to avoid being traced"
    When  the report is written
    Then  the register shows the marker instead and the lint lists "ethics guard (evasion)"

  @S-plans-012
  Scenario: the timeline is sorted by time and numbered, from the publish date
    Given publish date 2026-11-02 and steps at T+3d 10:00, T0 09:00 and T-1d 15:00
    When  plans run
    Then  T.md lists them T-1d, T0, T+3d numbered 1-3 with their dates 2026-11-01, 2026-11-02, 2026-11-05 and white or gray labels

  @S-plans-013
  Scenario: the stricter label of writer and checker wins, and black never enters the timeline
    Given the writer labels three steps white and the checker labels them gray, black and white
    When  plans run
    Then  the timeline has the first as gray and the third as white; the second is in the excluded table, not the timeline

  @S-plans-014
  Scenario: a step outside the ticked means is dropped and disclosed
    Given the user ticked only white and a step is labelled gray
    When  plans run
    Then  the timeline holds no gray step and T.md lists the dropped step as outside the chosen means; with only black ticked the writer is asked to schedule no steps

  @S-plans-015
  Scenario: the excluded table appears only when black is ticked, and is scanned for evasion
    Given an excluded entry naming "sockpuppet accounts" whose lawful alternative is clean, and one whose exposure says "rotate IP addresses to avoid being traced"
    When  plans run with black ticked, and again without black
    Then  with black the table keeps the first entry and shows the evasion marker in the second; without black there is no table

  @S-plans-016
  Scenario: persona and evasion advice in a timeline step is sent back once, then removed
    Given the writer keeps proposing a step "seed comments from alt accounts"
    When  plans run
    Then  the retry prompt names the hit, and the step is not scheduled but listed as stopped by the ethics guard

  @S-plans-017
  Scenario: a step on or next to a sensitive date is warned, and the reviewer sees when each step runs
    Given publish date 2027-02-26 in tw and steps at T0, T+1d and T+2d
    When  plans run
    Then  the T+1d and T+2d steps carry a warning naming 228 Peace Memorial Day, T0 none, and the reviewer's prompt holds each step's day and time

  @S-plans-018
  Scenario: plan A never changes a locked sentence
    Given the card locks "我們的產品很棒棒，大家都喜翻。" and plan A rewrites that paragraph
    When  plans run
    Then  A.md keeps the sentence and a warning names the dropped change; a locked sentence not found in the text is warned; a change that wraps it in other words is dropped; an inserted paragraph right after it is warned; a locked sentence the guard would flag (a denial such as "我們沒有僱用網軍。") is kept

  @S-plans-019
  Scenario: the revision is re-audited at quick depth by the same panel
    Given an outbound run whose plan A changed a paragraph
    When  the reaudit phase runs
    Then  every (quick unit, model) reviews A.md, the result is marked provisional, and the original reviews are untouched; a changed A, intake, matrix or context starts it afresh

  @S-plans-020
  Scenario: no re-audit when there is nothing revised, or no revision for the direction
    When  the reaudit phase runs where plan A changed nothing, and for an inbound run
    Then  no model is called and the status is unchanged, or not_applicable

  @S-plans-021
  Scenario: every stage's output is reviewed by a model from another vendor
    Given the roster claude:opus, openai:gpt-5
    When  plans run
    Then  openai:gpt-5 reviews A, B, C, the timeline and the excluded table, and the report lists each stage with its writer, reviewer and result; a relabel counts only when the reviewer's stricter label won, the withheld count includes entries withheld because the review failed, and the reviewer's reasons pass the guard

  @S-plans-022
  Scenario: an excluded entry the reviewer finds too operational is withheld
    Given the reviewer flags the second excluded entry as giving steps
    When  plans run
    Then  that entry keeps its tactic, law and alternative, and its exposure and watch-for text are withheld with the reviewer's reason

  @S-plans-023
  Scenario: a stage whose review failed is shown as not reviewed
    Given the reviewer fails on the kit
    When  the report is written
    Then  the stage table shows C as not reviewed, with the reason
  @S-plans-024
  Scenario: two labels for one step keep the stricter, and misnumbered labels void the review
    Given the reviewer labels step 1 black and then white, or numbers its labels from 0 or past the last step
    When  plans run
    Then  step 1 is not scheduled and is in the excluded table; misnumbered labels leave every step not reviewed and the stage shown as invalid

  @S-plans-025
  Scenario: an excluded table the reviewer never reviewed is withheld
    Given the reviewer fails, or refuses
    When  plans run
    Then  no step is scheduled, and every excluded entry keeps its tactic, law and alternative while its exposure and watch-for text are withheld

  @S-plans-026
  Scenario: the reviewer's own text passes the guard, and naming a persona tactic survives rendering
    Given the reviewer's reason for a black label says to rotate IP addresses, and an excluded tactic is "A sockpuppet network posting praise"
    When  plans run
    Then  neither T.md nor T.json holds the evasion text, and T.md shows the tactic by name

  @S-plans-027
  Scenario: steps beyond the cap are disclosed, and the reviewer sees every scheduled field
    Given more steps than the cap, each with a stop condition
    When  plans run
    Then  the extra steps are listed as not scheduled (too many) and the reviewer's prompt holds the stop conditions

  @S-plans-028
  Scenario: an unreadable publish date is disclosed
    Given the publish date "next Friday"
    When  plans run
    Then  T.md names it as unreadable, so no dates or sensitive-date warnings are given
  @S-plans-029
  Scenario: press before the affected parties, and a paid step without a stop condition, are warned
    Given steps "tell affected customers" (affected) at T0 10:00, a press release (press) at T0 09:00, and a paid boost (paid, no stop)
    When  plans run
    Then  the press step warns that it comes before the affected parties and the paid step warns that it has no stop condition; a tie or a missing time counts as early; in a crisis posture a plan with no affected step warns; staff after the public warns

  @S-plans-030
  Scenario: plan C monitoring keywords are typed terms
    When  plan C returns keywords with a kind and platforms
    Then  C-kit.md lists them by kind; a keyword that looks like an account handle or a link (@, ＠, u/, t.me/, URLs) is dropped and counted without repeating it; malformed entries are skipped or normalised
  @S-plans-031
  Scenario: in a crisis posture, no promotion before the affected parties are helped
    Given a promotional step at T0 09:00 and the step telling affected customers what to do at T0 10:00, under clarify_apologize; and the same under promote
    When  plans run
    Then  the promotional step warns under clarify_apologize and not under promote

  @S-plans-032
  Scenario: the exchange or regulator hears first
    Given an exchange filing at T0 16:00 and a press release at T0 09:00
    When  plans run
    Then  the press release warns that it comes before the filing

  @S-plans-033
  Scenario: a public step while claims are unverified is warned
    Given the ledger holds a claim that is cannot_verify and the timeline has a press step
    When  plans run
    Then  the first press or public step warns and names the claim id
  @S-plans-034
  Scenario: plan A's changes to protected details are disclosed
    Given a paragraph "Revenue grew 40% in 2025, said 「CEO」." that plan A rewrites as "Revenue grew 45% in 2025."
    When  plans run
    Then  a warning names the paragraph, the removed "40%" and quote and the added "45%"

  @S-plans-035
  Scenario: advice to evade AI detection or to sound like an independent user is a hit
    When  the guard reads "Humanize the copy so it passes AI detection", "降低AI率，去AI味", "make it sound like an ordinary customer" and "像普通網友一樣留言"
    Then  each is a hit; "Never use tools that bypass AI detection" and "we do not claim the text is AI-generated" are not
  @S-plans-036
  Scenario: a step that publishes an election poll inside a blackout is not scheduled
    Given tw's 2026 poll blackout from 11-18 to 11-28 and publish date 2026-11-15, with a poll step at T+5d and another at T+1d
    When  plans run
    Then  the T+5d poll step is dropped and disclosed as inside the blackout, and the T+1d step stays
```

## Must NOT
- @N-plans-001 a plan reaches the user with concealment, persona or laundering text that the guard found and nobody was told
- @N-plans-002 a step that the writer or the checker labelled black, or that is outside the ticked means, appears in the timeline

## Revisions
- 2026-10-22 · forked from ant-peer-review @3ddd7f5 and rewritten for PR risk review; ids restart in this repo · decision: D-PR-1
- 2026-10-22 · +S-plans-012..020 timeline of means, excluded black tactics, locked sentences, re-audit · decision: D-0002
- 2026-10-22 · +S-plans-021..023 every stage reviewed by another model (user: 每個階段的產出都要另一個 model 審) · decision: D-0002
- 2026-10-22 · +S-plans-024..028, ~S-plans-018 (a lock not found is warned), ~S-plans-019 (the re-audit restarts when the intake, matrix or context change), from the tier-3 review · decision: D-0002
- 2026-10-22 · ~S-plans-014, 016, 017, 018, 021, 024 from the second tier-3 review (fable): a guard-flagged step is never scheduled, misnumbered labels void the review, sentence-boundary locks, ±1 day warnings · decision: D-0002
2026-10-22 · +S-plans-029..030 timeline audience rules, typed monitoring keywords · decision: D-0003
- 2026-10-22 · ~S-plans-029, 030 from the tier-3 review · decision: D-0003
- 2026-10-22 · +S-plans-031..033 harm first, disclosure first, stage the launch (borrowed) · decision: D-0003
- 2026-10-22 · +S-plans-034..035 protection-list diff, AI-detection and independent-voice evasion (borrowed from wepr; ethics guard D-PR-7) · decision: D-0003
- 2026-10-22 · +S-plans-036 poll blackout (borrowed from med-political) · decision: D-0003
