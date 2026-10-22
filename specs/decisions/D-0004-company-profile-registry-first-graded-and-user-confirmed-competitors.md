# D-0004 Company profile: registry first, graded and user-confirmed competitors

| | |
|---|---|
| Status | accepted |
| Decided | 2026-10-22 |
| Features | company-profile |
| Glossary term | |
| Authority | user, 2026-10-22: "評估是否值得需要輸入公關當事人，如公司名稱/統編，然後 model 再去搜尋/找出產業別/競爭對手清單等" — my evaluation (registry, sourced search, user ticks) was accepted with the order "角色＋借鏡檢查題 → 統編 → 撰寫" |
| Guard | tests/test_profile.py |
| Migration | runs created earlier read the new profile phase as done (Run.state); an intake without a tax ID skips the lookup |
| Related | D-PR-9 (context scan consent), D-PR-10, D-PR-12 (search provenance), docs/REFERENCES.md #10, #17, #18 (grades, scoped absence, independence) |

## Decision

- The tax ID (統一編號) is validated in code first: 8 digits, with the checksum (divisible by 10, or by 5 under the 2023 rule). Nothing is sent for an invalid ID.
- **Registry first**: Taiwan's GCIS open data, fetched by the honest-UA crawler (robots, address checks). The two datasets read are basic company data and business items. We keep the name, status, set-up date, capital, registering office and business items. The representative's name and the address are dropped on read: they are never stored, prompted or reported.
- **Industry** comes from the business-item codes (their letter sections) and the item names.
- **Competitors**: one search call by a search-capable (Claude) model. Only evidence whose URL came back from a tool call counts (D-PR-12). The grades are A (registry, regulator, exchange filing), B (independent report) and C (company claim, aggregator, search lead). Sources on the same domain are one source. A competitor is confirmed with one A or two B on different domains; otherwise it is a lead. The roles are direct, indirect, substitute and benchmark.
- **The user ticks** what enters the context card (industry, competitors). A non-interactive run keeps only the confirmed.
- **Consent**:
  - an interactive run asks before the first request;
  - under embargo it asks again, defaulting to no, because even a name lookup reveals interest. `--company-lookup` alone never sends anything for embargoed material, so a non-interactive embargoed run skips the lookup;
  - a non-interactive run needs `--company-lookup`.
- An official grade (A) needs an official host (gov, nat.gov.tw, europa.eu, the exchanges); an official kind elsewhere is a claim (C). One outlet is one source across www., subdomains and country domains. Competitor names are cleaned and reach review prompts only as untrusted data; the tax ID never does.
- **Absence is scoped**: "no record in GCIS as of <date>", never "does not exist".
- The profile phase runs right after intake and writes the card fields `industry` and `competitors`, so every later phase sees them.

## Why not the alternative

- A model listing competitors from memory: unsourced and unverifiable.
- Storing the whole registry row: it carries personal data the review does not need.

## Deliberately not done

- US (SEC EDGAR), the stock-exchange filings (MOPS) and EU registries are planned.
- China's enterprise credit system needs a captcha: never automated, so search only.
- Monitoring the competitors.

## Why a new record

D-PR-9 governs the context scan; the profile adds a registry API, source grades and a privacy rule for registry personal data
