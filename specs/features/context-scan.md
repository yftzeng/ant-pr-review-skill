# Feature: context scan

Before the review, sensitive dates near the publish date are taken from the
packs (no web), and recent news about the named parties and topic is searched,
only after the user confirms the queries and never under embargo (D-PR-9).
A finding counts only if its URL came back from a tool call.

```gherkin
Feature: context scan
  @S-context-scan-001
  Scenario: under embargo nothing reaches the web
    Given an embargoed outbound run
    When  the whole pipeline runs
    Then  no model call carries a tool, the context status is "embargo" and claims are cannot_verify "embargo"

  @S-context-scan-002
  Scenario: queries are shown and run only after confirmation
    Given named party "Acme" and an interactive run
    When  the user declines the queries, or accepts them
    Then  declining makes no search and records "skipped"; accepting runs each query with WebSearch

  @S-context-scan-003
  Scenario: a non-interactive run searches only with --context-scan
    When  a --yes run has no --context-scan
    Then  the context status is "skipped" and no search is made

  @S-context-scan-004
  Scenario: a finding without a searched URL is dropped
    Given the searcher returns two findings, only one with a URL from its tool results
    When  the query runs
    Then  one finding is kept and the drop is noted

  @S-context-scan-005
  Scenario: without a Claude model nothing is searched
    Given the roster openai:gpt-5 and gemini:gemini-2.5-pro
    When  context and fact-check run
    Then  the context status is "no_search_backend" and claims are cannot_verify "no_search_backend" with no call

  @S-context-scan-006
  Scenario: lifting the embargo lets the fact-check run later
    Given an embargoed run with pending claims
    When  "factcheck <run> --continue --lift-embargo --yes --finalize" runs
    Then  the claims are checked with search and the next report version is written
```

## Must NOT
- @N-context-scan-001 a web search runs for an embargoed run, or before the user agreed to the queries

## Revisions
- 2026-10-22 · +S-context-scan-001..006 +N-context-scan-001 · decision: D-PR-9 -- new: unreleased material must not leak through search queries
