# Feature: context card

Intake asks the direction (outbound, operation, inbound), the targets, and a
context card: our organisation, named parties, jurisdictions (checkbox, default
Taiwan), channels, stakeholders, publish date, topic keywords and embargo. The
card is shown for confirmation and can be edited field by field.

```gherkin
Feature: context card
  @S-context-card-001
  Scenario: targets are classified and echoed until /done
    When  the user enters a URL, an existing path and a line of text, then "/done"
    Then  three targets of kind url, path and text are returned, each echoed with its number

  @S-context-card-002
  Scenario: two empty lines or Ctrl-D also end the list
    When  the user enters one URL and then two empty lines, or Ctrl-D
    Then  the list ends with one target

  @S-context-card-003
  Scenario: consecutive text lines become one text target
    When  the user pastes three lines of text
    Then  they form one text target

  @S-context-card-004
  Scenario: an empty target list asks again
    When  the user ends the list without a target, then gives one
    Then  the need-a-target message is shown and one target is returned

  @S-context-card-005
  Scenario: jurisdictions are a checkbox, Taiwan by default, at least one
    When  the card is filled and the jurisdiction checkbox is confirmed as is, or with US and EU ticked
    Then  the jurisdictions are ["tw"], or ["tw", "us", "eu"]; un-ticking all is refused

  @S-context-card-006
  Scenario: the card can be edited before confirming
    Given a filled card
    When  the user edits the named parties and confirms
    Then  the card holds the new parties and the other fields are unchanged

  @S-context-card-007
  Scenario: non-interactive intake from arguments
    When  intake is built from --direction operation --jurisdictions tw,cn --party "A, B" --channels kol,forums --embargo
    Then  the intake holds direction "operation", jurisdictions ["tw", "cn"], parties ["A", "B"], channels ["kol", "forums"], embargo true

  @S-context-card-008
  Scenario: unknown jurisdictions, channels or directions are refused
    When  intake is built with jurisdiction "jp", channel "tv" or direction "sideways"
    Then  each is a ValueError naming the allowed values

  @S-context-card-009
  Scenario: embargo defaults to yes for outbound and no otherwise
    When  the embargo question is answered with Enter for an outbound and an inbound review
    Then  embargo is true for outbound and false for inbound
```

## Revisions
- 2026-10-22 · forked from ant-peer-review @3ddd7f5 and rewritten for PR risk review; ids restart in this repo · decision: D-PR-1
