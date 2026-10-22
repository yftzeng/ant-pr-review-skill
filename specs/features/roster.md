# Feature: roster

The reviewer roster spans vendors (D-PR-4): Claude through `claude -p`, and
OpenAI, Gemini, Grok and OpenRouter through OpenAI-compatible HTTP. It is picked
by checkbox with arrow keys (at least 2), each pick is probed, and every run
prints the reviewers with their vendor. A roster from one vendor is allowed but
highlighted with its blind-spot risk.

```gherkin
Feature: roster
  @S-roster-001
  Scenario: first use preselects claude:opus and claude:sonnet and offers every provider
    Given no saved config
    When  first-use setup runs and the user confirms the checkbox
    Then  the saved models are ["claude:opus", "claude:sonnet"]
    And   the checkbox listed models of claude, openai, gemini, grok and openrouter

  @S-roster-002
  Scenario: fewer than two reviewers is refused
    When  the user ticks only one model, then two
    Then  the menu says at least 2 are needed and saves the two

  @S-roster-003
  Scenario: every run prints the reviewers with their vendor and how to change them
    When  the banner is printed for claude:opus and openai:gpt-5
    Then  it lists "claude:opus [anthropic], openai:gpt-5 [openai]" and the config models hint

  @S-roster-004
  Scenario: config models re-shows the checkbox with the saved choice ticked
    Given saved models ["claude:opus", "openai:gpt-5"]
    When  "config models" runs and the user confirms
    Then  the saved models are unchanged

  @S-roster-005
  Scenario: a model that fails its probe is not saved
    Given openai:gpt-5 fails its probe
    When  claude:opus, claude:sonnet and openai:gpt-5 are ticked
    Then  the saved models are claude:opus and claude:sonnet and the failure reason is shown

  @S-roster-006
  Scenario: interface strings follow the chosen language and every locale has every key
    Given language "zh-TW"
    When  the direction question is shown
    Then  it is the zh-TW string; en, zh-TW and zh-CN have the same keys; every key the code uses exists

  @S-roster-007
  Scenario: a one-off override does not change the saved config
    Given saved models ["claude:opus", "claude:sonnet"]
    When  a run starts with --models claude:opus,gemini:gemini-2.5-pro
    Then  the run uses those two and the saved models are unchanged

  @S-roster-008
  Scenario: questions, information, warnings and phases look different from each other
    Given output that is not a terminal
    When  a question, the banner, a warning and a phase start are printed
    Then  they start with "? ", "ℹ ", "⚠ " and "━━", and no ANSI escape codes are printed

  @S-roster-009
  Scenario: a single-vendor roster is highlighted and explained, never blocked
    Given models claude:opus and claude:sonnet
    When  the banner is printed and a run synthesizes
    Then  the banner carries the "⚠" single-vendor warning with its blind-spot explanation
    And   the synthesis warns "single_vendor" and the run still completes

  @S-roster-010
  Scenario: vendors are told apart, including OpenRouter paths
    When  the vendors of claude:fable, gemini:gemini-2.5-pro, grok:grok-4 and openrouter:anthropic/claude-x are read
    Then  they are anthropic, google, xai and anthropic, and a mixed roster has no warning

  @S-roster-011
  Scenario: a custom provider:model can be added from the checkbox
    When  the user adds "openrouter:mistralai/mistral-large" with "c"
    Then  it is probed and saved

  @S-roster-012
  Scenario: aliases are normalized and malformed models refused
    When  --models "opus,sonnet" and then --models "opus,acme:x" are given
    Then  the first becomes claude:opus,claude:sonnet and the second is a usage error naming acme:x
```

## Must NOT
- @N-roster-001 the user store is written inside the installed skill directory

## Revisions
- 2026-10-22 · forked from ant-peer-review @3ddd7f5 and rewritten for PR risk review; ids restart in this repo · decision: D-PR-1
