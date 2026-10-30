# Feature: crisis

When something has just happened, the user picks "crisis" (first in the menu),
pastes what they have (text, files or links) and is asked nothing more. A few
model calls later the run holds a printable response sheet in the run's language:
crisis.md, with crisis.pdf and crisis.docx beside it. The sheet covers the first
hours: the team's roles, the first 30 minutes, the fact sheet, the damage, the
holding statement and its channel versions, the Q&A, the timeline, who to tell in
what order, the legal checklist for counsel, the questions for the business head,
the other side's case, press-conference preparation, an update log and the
sign-off. Every unknown is a blank to fill in by hand. Nobody is named (D-0007).

```gherkin
Feature: crisis
  @S-crisis-001
  Scenario: crisis is first in the purpose menu and asks nothing after the event
    When  an interactive intake answers "1" at the purpose question, then pastes the event text and /done
    Then  no other question is shown, the purpose is "crisis", the means are white, gray and black (gray needs approval, black is assessed and never scheduled), the posture clarify_apologize, the card not characterised and under embargo (no web calls), the jurisdictions the default
    And   an Enter at the purpose question still keeps "audit"

  @S-crisis-002
  Scenario: crisis runs from the command line with only targets
    When  "ant-pr-review new --yes --purpose crisis --target <text>" runs, and when no target is given
    Then  the first makes a crisis run named after its text; the second is refused with "at least one --target"; --brief with crisis is refused

  @S-crisis-003
  Scenario: a crisis run reads its sources and writes the sheet with a few calls and no prompt
    Given a crisis run whose one URL target cannot be read and one text target
    When  the pipeline runs interactively
    Then  the sources phase asks nothing and goes on with the text, the crisis phase calls only crisis_facts, kit, opponent, timeline and classify_means, every other phase is marked done as not applicable, and the run is finished
    And   an audit or drafting run marks the crisis phase not applicable and calls nothing for it

  @S-crisis-004
  Scenario: the sheet has every section in order, in the run's language, with PDF and DOCX
    Given a zh-TW crisis run with the fake backend
    When  the crisis phase runs
    Then  crisis.md has, in order: the bottom line with a suggested grade marked unconfirmed, the objective, the team roles, the first 30 minutes (including pausing promotions and the gag order), the fact sheet (5W1H, the three times, verified, pending with owner and due, rumours), the damage, the holding statement with its six parts and channel versions, the Q&A and frontline Q&A, phrases not to say, the timeline, who to tell in priority order and the media list, the legal checklist marked for counsel, the questions for the business head, the other side's case, press-conference preparation, the update log, the sign-off and the next steps
    And   crisis.pdf and crisis.docx are written beside it with the same section headings, and the headings come from the zh-TW locale

  @S-crisis-005
  Scenario: the fact sheet is checked in code
    Given a crisis_facts answer with a rumour marked false and no counter-evidence, a rumour marked false with one, a pending item with no owner or due, a media entry "@reporter_x", an unknown signal and minors true
    When  the sheet is built
    Then  the first rumour reads unverified, the second false with its counter-evidence, the pending owner and due print as the blank 〔　　〕, the media entry is dropped with a warning, the unknown signal is dropped, the suggested grade is the highest of the known signals and says it is the model's suggestion for the user to confirm, and minors prints only yes with the bottom-line flag

  @S-crisis-006
  Scenario: the prompt keeps people out of the sheet
    When  the crisis_facts prompt is built
    Then  it says roles and counts only, never the name of a victim, employee, whistle-blower, reporter or influencer; outlets by name only; minors as yes or no; a rumour false only with counter-evidence from the material; and the material is untrusted data

  @S-crisis-007
  Scenario: without the export packages the sheet is still written
    Given the export packages cannot be imported
    When  the crisis phase runs
    Then  crisis.md is written, no PDF or DOCX exists, and the run says why with the install command
  @S-crisis-008
  Scenario: gray steps need approval, black tactics are assessed and never scheduled
    Given a crisis timeline with a white step, a gray step with its disclosure and a black step
    When  the sheet is built
    Then  the white step is listed plainly, the gray step is listed with "needs approval" and an approval box, the black step is not scheduled and appears under "assessed, not used" with the law, what to watch for and the lawful alternative

  @S-crisis-009
  Scenario: the sheet anticipates the other side's gray and black tactics and how to defend
    Given a threats answer naming astroturfing, an intrusion, an anonymous letter, a false flag and an unknown kind, one entry whose text advises avoiding detection and one naming a person's handle
    When  the sheet is built
    Then  a section lists each known kind with why it is likely here, early signs in the content, how to verify, what to do now, where to report and the law; the unknown kind is dropped, the evasion text is removed by the guard, the handle is removed, and at most ten entries are kept
    And   fixed lists made in code follow: the first hour of security (reset privileged passwords, multi-factor sign-in, sign-in logs, keep the logs), one official channel against impersonation, what staff must not do (answer, contact the source, hit back from personal or alt accounts) and how to handle an anonymous letter (do not pass it on, do not answer its details, preserve it, give it to counsel)
    And   the prompt says defence only, never how to run a tactic or avoid detection, never who is behind an account, signs from the content only
```

## Must NOT
- @N-crisis-001 Once crisis is chosen, no question is asked: not in the intake, the sources, the matrix or the plans.
- @N-crisis-002 A crisis run never schedules a black step, and never prints a gray step without "needs approval".
- @N-crisis-003 The other side's tactics are described for defence only: never how to run one, never how to avoid detection, never who is behind an account. The prompt is the control; the guard is pattern-limited (ethics.py): evasion in every field, and in what we do (verify, defend, report) any persona word unless negated, so those columns say "suspicious accounts".

## Revisions
- 2026-10-30 · created · decision: none -- no feature runs without questions from the event alone; audit and drafting both ask an intake, a card or a brief
- 2026-10-30 · +S-crisis-001..007, +N-crisis-001..002 the crisis purpose, its sheet and its checks (user: 就用 crisis，然後放在第一個 … 選 crisis 時不會再問用戶任何問題，直接生成 printable a4 pdf，含所有相關素材; 開工) · decision: D-0007
- 2026-10-30 · ~S-crisis-001 ~N-crisis-002 +S-crisis-008..009 +N-crisis-003 gray steps need approval, black is assessed, and the other side's gray and black tactics are anticipated for defence (user: 我認為應該考慮灰色與黑色手段，因為這是從政治及商業競爭對手會採用的攻擊手法 …; 開工，灰色開放但標需核准) · decision: D-0007
