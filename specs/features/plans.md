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
```

## Must NOT
- @N-plans-001 a plan reaches the user with concealment, persona or laundering text that the guard found and nobody was told

## Revisions
- 2026-10-22 · forked from ant-peer-review @3ddd7f5 and rewritten for PR risk review; ids restart in this repo · decision: D-PR-1
