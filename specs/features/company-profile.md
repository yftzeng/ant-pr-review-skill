# Feature: company profile

Before the review, the user may give our company's tax ID (統一編號). The tool reads the
official registry (Taiwan's GCIS open data) for the company's name, status, set-up date,
capital, registering office and business items, from which the industry is drawn. With
a search-capable model it then looks for competitors. Each competitor needs sources that
the search tool returned, graded A (registry or regulator), B (independent report) or
C (company claim or a lead). A competitor is confirmed with one A or two B sources from
different domains, otherwise it is a lead. The user ticks which go into the context
card. Nothing is looked up without consent; under embargo the user is asked again. The
registry's personal data (the representative's name, the address) is never stored.

```gherkin
Feature: company profile
  @S-company-profile-001
  Scenario: a tax ID is validated before anything is sent
    When  the tax ID is "22099131", "2209913" or "22099132"
    Then  the first is valid; the second (7 digits) and the third (bad checksum) are refused without a lookup

  @S-company-profile-002
  Scenario: the registry gives the company facts and its business items, never the representative
    Given the registry answers for 22099131 with a name, status, capital, a representative name, an address and business items
    When  the profile is built
    Then  it holds the name, status, set-up date as ISO, capital, registering office, business items and their industries, with the source URLs and the access date, and holds neither the representative's name nor the address

  @S-company-profile-003
  Scenario: nothing found is reported as scoped absence
    Given the registry answers an empty list
    When  the profile is built
    Then  it says no record was found in GCIS on that date, never that the company does not exist

  @S-company-profile-004
  Scenario: competitors are graded by their sources and only searched sources count
    Given the searcher returns competitor X with a regulator source, Y with two independent sources from different domains, Z with two independent sources from one domain, and W with a URL the search never returned
    When  the profile is built
    Then  X and Y are confirmed, Z is a lead (one outlet is one source, across www., subdomains and country domains), W's unsearched source is dropped, an official kind on a non-official host counts as C, and duplicate names merge

  @S-company-profile-005
  Scenario: the user ticks which competitors enter the card
    When  the competitor checkbox is confirmed with Enter, interactively; and in a non-interactive run
    Then  confirmed competitors are ticked and leads are not; the card holds the ticked names (cleaned of control and markup characters) and the industry; a non-interactive run keeps only the confirmed; review prompts show the names apart as untrusted data and never the tax ID

  @S-company-profile-006
  Scenario: no lookup without consent, and embargo asks again
    When  a non-interactive run has a tax ID but no --company-lookup; a run under embargo has --company-lookup but is non-interactive, or is interactive and answers the question with Enter; an invalid tax ID is given
    Then  no request is made in any case, the status is skipped, and the card's earlier industry and competitors are cleared

  @S-company-profile-007
  Scenario: the report shows the profile with its sources
    When  the report is written for a run with a profile
    Then  it has a company profile section with the registry facts and their source and date, the industry, and each competitor with its role, grade and sources, leads apart
```

## Must NOT
- @N-company-profile-001 the registry's representative name or address is stored, sent to a model or shown in the report

## Revisions
- 2026-10-22 · created · decision: none -- context-scan covers news about named parties with consent; a registry lookup by tax ID plus graded competitor search is a separate source with its own privacy rule (no representative names) and its own consent
- 2026-10-22 · +S-company-profile-001..007, +N-company-profile-001 the lookup, grades, consent and report (user: 角色＋借鏡檢查題 → 統編 → 撰寫) · decision: D-0004
- 2026-10-22 · ~S-company-profile-004..006 from the tier-3 review (embargo strict, invalid ID stops, outlets, official hosts, names as untrusted data) · decision: D-0004
