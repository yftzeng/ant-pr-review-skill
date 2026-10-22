# ant-pr-review — Design

Status: design agreed 2026-10-22 (user answers to the four open questions, plus the
checklist rule). Forked from ant-peer-review @3ddd7f5; see `docs/EVALUATION.md` for
the module-by-module evaluation that led here (the first zh-TW draft is in
`docs/archive/`).

A **public-relations publishing and operations risk review**, shipped as a Claude
skill plus a standalone Python CLI (`ant-pr-review`). The input is pasted text, a
folder or file, or article URLs. Several models, from several vendors where
possible, answer the same risk checklist independently, from stakeholder lenses
and per jurisdiction. They then cross-examine each other. Deterministic code
turns the answers into a risk register and a Go / Conditional / Escalate / No-Go
verdict, and writes plans A/B/C.

The skill, specs, prompts and checklists are in English. The CLI interface is
localized (en, zh-TW, zh-CN), and so is the README.

## 0. Terms

| Term | Meaning | Not to be confused with |
|---|---|---|
| White PR | Communication that is truthful, attributable and disclosed: press releases, statements, crisis replies, disclosed KOL deals, substantiated comparisons | "positive content", which may still be undisclosed advertising |
| Black PR | Attacking a party or steering opinion with false, anonymous, disguised or undisclosed means: smears, rumours, quotes out of context, sockpuppets and paid posters, astroturfing, fake reviews, staged "anonymous leaks" | "negative content": a substantiated, attributed criticism is white PR |
| Grey zone | Depends on method and disclosure: newsjacking, anonymous sourcing, counter-attacks, sponsored posts, comparative ads | — |
| Direction | `outbound` our content to publish; `operation` a dissemination or influence plan; `inbound` content aimed at us | — |
| Lens | The stakeholder seat a reviewer takes (legal counsel, hostile journalist, …) | Model: lens and model are orthogonal axes of the matrix |
| Unit | One (lens-group, jurisdiction-or-global) slot of the matrix; every model answers every unit | — |
| Checklist item | A fixed question (`LEG-01`) every model must answer for its unit | A risk: a free, anchored finding a model raises |

## 1. Decisions

| ID | Decision | Rejected alternative, and why |
|---|---|---|
| D-PR-1 | Fork ant-peer-review's infrastructure (sources, workspace, ui, factcheck provenance, report linter) into `ant_pr_review`. The upstream commit is recorded above | A shared core package: both are 0.1, so the interfaces are not stable yet. Extracting now would freeze both |
| D-PR-2 | **Both depths, chosen in the CLI** (radio): `quick`, where each model answers all global items in one call plus one call per jurisdiction; `full`, where each model answers each lens in its own call, per jurisdiction where the lens is jurisdiction-scoped | Only one depth. quick costs ~1/4 of full but dilutes opposing seats in one call. The user picks per run |
| D-PR-3 | **Every checklist item is answered by every model** (peer). Code checks coverage. A missing item gets one targeted retry, then is recorded `unanswered` and disclosed. Silence is never a pass | A model answering only what it finds relevant: an unanswered question would read as "no risk" |
| D-PR-4 | Multi-vendor roster: `claude:opus|sonnet|fable` (via `claude -p`), `openai:*`, `gemini:*`, `grok:*`, `openrouter:<vendor>/<model>` (OpenAI-compatible HTTP, stdlib only). Picked by checkbox with arrow keys, min 2. **A single-vendor roster is allowed** but highlighted in the banner and the report, with its blind-spot risk spelled out | Blocking single-vendor: the user decided it must not block. Claude-only: same-vendor errors correlate |
| D-PR-5 | Jurisdictions by checkbox: Taiwan, United States, European Union, China. Multi-select, default Taiwan. **Each jurisdiction is reviewed by its own calls** (never one call for several). When 2 or more are ticked, an independent **merger** call compares the per-jurisdiction results after all are done. It sends questions back to each jurisdiction's reviewers (a discussion round), then writes a consolidated report plus one report per jurisdiction | One call covering all jurisdictions: answers get shallow, and differences blur |
| D-PR-6 | Synthesis is a **risk register**: likelihood 1-5 × impact 1-5 per risk, the max over supporters, with the spread shown. A red-line veto sits on top. The verdict is Go / Conditional / Escalate / No-Go and is computed by code. The consolidated verdict is the worst per-jurisdiction verdict | A weighted quality score: averaging hides the one risk that sinks a launch |
| D-PR-7 | **Ethics guard enforced in code**: plans may only move toward lawful, disclosed and provable communication. A linter blocks four things: advice on evading detection or attribution; batches of fake-persona comments; keeping an unsupported allegation sentence verbatim; and an "improved operation" (the `operation` plan-B schema has no field for one). On a hit: one retry, then the passage is removed and the removal disclosed | A prompt rule only: injection and model drift bypass prompts |
| D-PR-8 | Laws live in **jurisdiction packs** (`jurisdictions/<j>.toml`): reference, summary, regulators, platforms, sensitive dates, `verified = false` until checked. Law citations a model relies on become `legal_citation` ledger claims and are fact-checked | Laws hard-coded in prompts: they change, and models misremember article numbers |
| D-PR-9 | **Context scan** phase: queries built from the context card, shown to the user and run only on confirmation (or `--context-scan`). Results are kept only if their URL came back from a tool call. `--embargo` (or "embargoed" on the card) disables every web call: context is skipped and claims become `cannot_verify:embargo` | Always searching: an unreleased announcement's keywords would leak to a search engine |
| D-PR-10 | `inbound` reviews the content only: which allegations are verifiable, textual signs of coordination inside the given material, and the risk of each response option. It never profiles or identifies the people behind accounts | Tracing people: that becomes a doxxing tool; tracing belongs to lawyers and platforms |
| D-PR-11 | Synthesis, tallies, verdicts and per-jurisdiction splits are deterministic code (as upstream D-12). Only the merger narrative (differences, questions) is a model call, and its output never changes a verdict | LLM synthesis: it can invent or drop findings, and it is not free to recompute |
| D-PR-12 | Web tools (fact-check, context scan) run only through `claude -p`, where search provenance can be verified (upstream D-13). With no Claude model in the roster, those claims are `cannot_verify:no_search_backend` | Trusting another vendor's cited URLs without tool-result provenance |
| D-PR-13 | Every report carries "not legal advice". An Escalate verdict lists the concrete questions for counsel | — |
| D-PR-15 | Fetch fallback order: (1) the honest-UA crawler with bounded retries on 429/502/503/504 (Retry-After, capped, within the deadline); (2) a headless browser (Playwright, optional extra `render`) only for thin JS-rendered pages or `needs_js` site profiles, every browser request checked like the crawler's; (3) the page's AMP version, then the newest Wayback Machine snapshot, labelled with its date; (4) the user pastes the text or passes a saved file. robots, a site-profile block, internal addresses, a login or paywall (in the page or as 401/402) and 451 never fall back; a 403 or a bot challenge uses the archive only with the user's consent (asked interactively with the archive date, or `--archive-on-block`), never the browser; a URL carrying secrets is never sent to the archive. The browser fetches every request itself without following redirects, checks each Location and every navigation, refuses popups and WebSockets, and sends our UA. Synced with ant-peer-review D-0001 | curl or a browser that spoofs a regular browser's User-Agent or TLS fingerprint: its only use is getting past a site's refusal, the evasion this tool's ethics guard forbids. Archive copies of robots-denied pages: same reason |
| D-PR-16 | Posture (clarify_apologize, the default / promote / expose / rebut) adds its own checklist items; expose is on the record only, leaking through unattributed third parties is a black means. The ticked means (white / gray / black) shape only the plan's timeline; reviewers judge every item from all three angles. The timeline is labelled again by a reviewer from another vendor, and the stricter label wins. Black is never scheduled: it is assessed in an excluded table (law, how it is exposed, what to watch for, lawful alternative). Every stage's output (A, B, C, timeline, excluded table) is reviewed by another vendor's model. Outbound A is re-audited at depth quick. Locked sentences are never changed. The report checklist is a checkbox list with pass-rate bars. See specs/decisions/D-0002 | Scheduling black steps when ticked: an execution plan for deception (D-PR-7). Trusting the writer's own labels |
| D-PR-17 | Our role: a standpoint (responsible by default, affected, related) and identities, each a reasonable pair of a standpoint and a party type (e.g. responsible:organization, affected:victims); astroturf and the Chinese party and state organs are never our identity; a stored identity is re-validated on every read. Party types in seven groups (parties.toml, from the user's definitions; politics from each pack's parties and organs) make a stakeholder map: a jurisdiction-scoped `stakeholders` lens asks one item per group (STK-01..07), five role stress tests (RTM-01..05) and three political ones (POL-01..03), and every model answers every party type (relevance, reaction, needs, handling, L×I) — a missing type is a gap. Role items (ROL-*) are asked only for a matching identity. Borrowed items are credited in docs/REFERENCES.md. See specs/decisions/D-0003 | 20 separate checklist items; assessing only the parties the user ticks |
| D-PR-18 | Company profile: a valid Taiwan tax ID is looked up in the GCIS registry by the honest crawler (name, status, set-up date, capital, registering office, business items; never the representative or the address), the industry comes from the business-item sections, and a search model proposes competitors whose searched sources are graded A/B/C; one A or two B on different domains confirms, the rest are leads; the user ticks what enters the card. Never without consent; asked again under embargo; `--company-lookup` for `--yes`. See specs/decisions/D-0004 | A model listing competitors from memory; storing the whole registry row |
| D-PR-14 | Dropped from the fork: recheck, S-curve, the weighted rubric. ~~Drafting mode~~ **reversed 2026-10-22 by D-PR-19** (the user asked for it back) | Outside a risk review; recheck can come back later by re-running on the revised text |
| D-PR-19 | Drafting mode (D-0005): a fixed brief (facts confirmed / alleged / unknown, kind, emotion, outcome, decision, actions, approvers, tier-4 flags) plus optional material read only to check facts; two versions that differ in approach under the chosen posture, a near-duplicate retried once then dropped; another model reviews them against the brief; each is audited by the same matrix (round 1, provisional); code ranks (disqualified, verdict, top score, pass rate) and a model writes the reason with the numbers; the recommended version goes through the full review. A claim register (public, internal only, not supportable, needs validation) is enforced in code; gaps stay `[待查證]` and block the ready-to-publish file, never the report. Facts not yet characterising the event (cause and scope unconfirmed, the default) give holding statements only; cannot-commit lines are matched in code and block the export | One version: nothing to compare. Model-chosen recommendation: unverifiable and easy to sway. Drafting outside the matrix: the draft would skip the review it exists to pass |
| D-PR-20 | Event assessment (D-0006): the user ticks observed signals on the card; code grades I–IV, the higher grade wins, bottom lines (safety, illegality, minors), drafting tier-4 injury/crime/minors and confirmed red lines give grade I; the grade names who handles it and whether plan C is activated (I-II), on standby (III) or not (IV). The report opens with grade, risk outlook, action (with the three control axes) and activation. Not characterised gives a kit with a holding statement only; timeline steps carry the attention stage and one silence point | A model-assigned grade: unverifiable. Averaging signals: one grade-I signal must not be averaged away. Department-by-department intake: long, and internal material that should not go to a model |

## 2. Commands

```
ant-pr-review                         new run (or resume an unfinished one)
ant-pr-review new --yes --direction outbound --target <url|path|text> ...
      [--jurisdictions tw,us,eu,cn] [--depth quick|full] [--lenses legal,journalist,...]
      [--party "<name>" ...] [--org <name>] [--channels ...] [--publish-at <date>]
      [--embargo] [--context-scan] [--models claude:opus,openai:gpt-5] [--merger <model>]
      [--role responsible:organization ...] [--posture clarify_apologize|promote|expose|rebut]
      [--means white,gray,black] [--tax-id 22099131 --company-lookup]
      [--speaker ...] [--background ...] [--locked "<sentence>" ...] [--focus ...]
ant-pr-review resume <run> | rerun <run> --from <phase> | runs [--summary]
ant-pr-review factcheck <run> --continue [--yes --finalize]
ant-pr-review decide <run> [--yes --choice A|B|manual|hold --rule <red_line>=confirmed|dismissed]
ant-pr-review config models|lang|show
ant-pr-review lessons new|list|archive
```

Exit codes as upstream: 0 done, 3 paused (decision gate, backend failure), 2 usage, 130 interrupted.

## 3. Phases

| Phase | What | HITL |
|---|---|---|
| intake | direction (radio), our role: standpoint (checkbox, default responsible) then identities (checkbox of reasonable pairs), posture (radio, default clarify_apologize), means (checkbox, default all), targets, context card: our org, named parties, jurisdictions (checkbox, default tw), channels (checkbox), stakeholders (checkbox), publish date, topic keywords, embargo, speaker, background, locked sentences, focus | card confirm |
| profile | with consent: registry lookup by tax ID, graded competitor search, user ticks competitors; writes the card's industry and competitors (D-0004) | consent, competitor ticks |
| sources | crawl / convert / anchor / injection scan (upstream) | — |
| context | sensitive-date check (from packs, no web), then queries → confirm → `claude -p` WebSearch → provenance filter → `02-context.json` | query confirm |
| matrix | depth (radio), lenses (checkbox, defaults per direction), shows the units × models and the call count, locks `03-matrix.json` | confirm |
| review | each (unit, model) blind: orientation, every checklist item, risks, claims, red lines, worst headlines | — |
| factcheck | claims incl. `allegation`, `legal_citation`, `number` (upstream provenance) | — |
| debate | within each unit: corroborate/dispute others' risks, red lines and differing item verdicts | — |
| synthesis | per jurisdiction: global units + that jurisdiction's units → register, red lines, verdict; consolidated = worst | — |
| jmerge | ≥2 jurisdictions only: merger compare → per-jurisdiction discussion calls → merger final | — |
| plans | A minimal safe edit (char diff, locked sentences kept), B lawful alternative, C response kit; inbound: response-option comparison; T timeline of means plus the black-PR excluded table; every stage reviewed by a model from another vendor; ethics guard | — |
| reaudit | outbound only: A reviewed again at depth quick by the same models and jurisdictions, round 1 only (provisional) | — |
| report | consolidated report + one per jurisdiction, versioned: checklist as a checkbox list with pass-rate bars, revision diff and full text, re-audit before → after, timeline, excluded table, stage reviews | — |
| decision | rule contested red lines; choose A / B / manual / hold (do not publish) | decide |

## 4. Matrix

Lenses (`catalog.LENSES`); "scope j" means one unit per jurisdiction:

| Lens | Scope | Default for |
|---|---|---|
| legal — counsel, element by element | j | outbound, operation, inbound |
| journalist — hostile/investigative reporter; timing | global | outbound, operation |
| social — netizen communities of that jurisdiction | j | outbound, operation, inbound |
| target — the named party and its lawyer | global | outbound |
| regulator — regulators and platform trust & safety | j | outbound, operation |
| internal — employees, investors, partners | global | outbound |
| whistleblower — the insider who leaks the plan | global | operation |
| threat — allegation breakdown, coordination signs in the text | global | inbound |
| response — options and their costs | global | inbound |
| stakeholders — every party type (seven groups, with the pack's political parties): how each faces and handles it; the stress tests | j | outbound, operation, inbound |

Units: `quick` → `global.all` + `<j>.all` for each jurisdiction; `full` → `global.<lens>` for each global lens + `<j>.<lens>` for each scoped lens and jurisdiction. Every model answers every unit. Example: outbound, full, tw+us, 3 models: (3 global + 3×2 scoped) × 3 = 27 round-1 calls, and the same number of debate calls.

## 5. Synthesis rules

- Item tally: per item, the verdict of each model (`pass < concern < fail`; `na`; `unanswered`). The reported verdict is the most severe one, labelled `AGREE-n/n` or `SPLIT`, with the debate notes. Unanswered items are listed.
- Risks are merged as upstream findings (duplicates via debate, silence ≠ agreement, SPLIT on a dispute). L and I are the max over supporters, the spread is shown, `WIDE` if spread ≥ 2.
- A risk resting on a `cannot_verify` claim is set aside as unverified, **except** in dimension `provability`, where an unprovable statement is itself the risk.
- Red lines: `fabrication_about_party, undisclosed_inauthentic, privacy_doxxing, election_law, market_manipulation, health_claims, hate_human_rights, illegal_other`. Confirmed when 2 or more supporters and no dispute. `fabrication_about_party` is also confirmed when an `allegation` claim is `unsupported` and someone flagged it (evidence first). Otherwise it needs a human ruling. Low severity is advisory.
- Verdict: confirmed red line → `no_go`; pending ruling → provisional; `max(L×I) ≥ 15` or a legal risk ≥ 12 → `escalate`; `max ≥ 8` → `conditional`; else `go`. Thresholds are in config.

## 6. Jurisdiction merge (D-PR-5)

1. `07-jmerge/compare.json`: the merger gets each jurisdiction's synthesis summary and returns the differences, plus questions addressed to jurisdictions.
2. `07-jmerge/discuss/<j>/<model>.json`: every model that reviewed jurisdiction j answers j's questions. It sees j's own results and the other jurisdictions' summaries, and may revise its position, with a reason.
3. `07-jmerge/final.json`: the merger writes the common risks, the per-topic differences, the strictest jurisdiction and per-jurisdiction notes.

The narrative goes into the consolidated report. Verdicts stay those of §5.

## 7. Workspace

```
runs/<YYYYMMDD-HHMM>-<slug>/
  state.json  00-intake.json  01-sources/  02-context.json  03-matrix.json
  04-reviews/<unit>/<model-slug>.json      05-debate/<unit>/<model-slug>.json
  factcheck/ledger.jsonl                   06-synthesis.json  07-jmerge/
  08-report.v<N>.md  08-report.v<N>.<j>.md  08-report.v<N>.json
  09-plans/A.md A.diff B.md C-kit.md rereview.json ethics.json
  10-decision.json  final.md
```

## 8. Backends

| Provider | Transport | Key | Base URL |
|---|---|---|---|
| claude | `claude -p` (isolated, upstream D-14) | Claude Code login | — |
| openai | OpenAI-compatible chat/completions | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| gemini | OpenAI-compatible endpoint | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| grok | OpenAI-compatible | `XAI_API_KEY` | `https://api.x.ai/v1` |
| openrouter | OpenAI-compatible | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |

The base URL can be overridden with `ANT_PR_REVIEW_<PROVIDER>_BASE_URL`. JSON is requested with `response_format: json_schema` where the provider accepts it, with a fallback to `json_object` and the schema written into the prompt. The output is always validated, with one retry. The offered model names are a starting list (`roster.CATALOG`); any `provider:model` can be added as a custom checkbox value. A model is saved only after it passes a probe.

Vendor of a model: the provider, except for openrouter, where it is the path prefix (`anthropic/…` → anthropic). One vendor → `single_vendor` warning, highlighted.

## 9. Known limits

- The ethics guard and the injection scan are pattern-based (en/zh). A paraphrase can slip past them.
- The timeline's white/gray/black labels are model judgements. Two vendors and the stricter label lower the risk of a mislabelled black step, but do not remove it. With a single-vendor roster the reviewer shares the writer's blind spots.
- The re-audit is round 1 only (no debate, no fact check), so its verdict is provisional.
- The company profile reads Taiwan's registry only; US (EDGAR), exchange filings (MOPS) and EU registries are planned; China's registry needs a captcha and is never automated.
- Political sides in the packs (ruling, opposition) change with elections; each carries an as-of date and is unverified.
- Sensitive periods that move every year (Lunar New Year, Qingming, election run-ups) are not in the packs; only fixed dates are.
- The jurisdiction packs are starting points and incomplete; `verified = false` until a fact-check confirms a citation. Escalate means a human lawyer.
- The context scan sees only what search engines index. Private groups and LINE chats are invisible to it.
- Non-Claude providers cannot run web tools here (D-PR-12).
- Model names in the catalog age quickly. The probe is the only proof that a model exists.
- The headless browser's requests are fetched by Playwright, which resolves DNS itself after our check (a rebinding window the pinned crawler does not have).
- WebSockets are refused by `route_web_socket`. With the current Chromium a socket from a fulfilled document does not connect anyway, so no test can show that guard failing.
