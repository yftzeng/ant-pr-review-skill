# Feature: backends

Each roster model is routed to its provider's transport (D-PR-4): Claude to an
isolated `claude -p`, the others to OpenAI-compatible chat/completions over
stdlib HTTP. Output is validated against the step's schema. Web tools exist only
on Claude (D-PR-12).

```gherkin
Feature: backends
  @S-backends-001
  Scenario: the router sends each model to its provider's transport
    When  claude:opus, openai:gpt-5 and openrouter:deepseek/deepseek-chat are called
    Then  claude:opus goes to the claude transport and the others to their own OpenAI-compatible transport

  @S-backends-002
  Scenario: an OpenAI-compatible call carries the key, the model id and a JSON schema
    Given OPENAI_API_KEY is set and ANT_PR_REVIEW_OPENAI_BASE_URL points elsewhere
    When  openai:gpt-5 is called
    Then  the request goes to that base URL + /chat/completions with "Bearer <key>", model "gpt-5" and response_format json_schema

  @S-backends-003
  Scenario: a provider that rejects json_schema falls back to json_object with the schema in the prompt
    Given the first request fails with an error naming response_format
    When  the call is retried
    Then  the second request uses json_object and the prompt contains the schema

  @S-backends-004
  Scenario: invalid output is retried, then reported as invalid_output
    Given the provider answers with JSON that fails the schema twice
    When  the call runs
    Then  it raises a backend error with reason "invalid_output"

  @S-backends-005
  Scenario: a missing key or a web tool request fails clearly
    When  openai:gpt-5 is called without OPENAI_API_KEY, or with tools
    Then  the error names OPENAI_API_KEY, or has reason "no_search_backend"

  @S-backends-006
  Scenario: a provider refusal is recorded as a refusal
    Given the provider answers with a refusal message
    When  the call runs
    Then  the result is refused with the refusal text and no data
```

## Must NOT
- @N-backends-001 a runtime dependency outside the Python standard library is needed to call a provider

## Revisions
- 2026-10-22 · +S-backends-001..006 +N-backends-001 · decision: D-PR-4 -- new: the fork had one vendor
