# Reference skills

The skills reviewed while designing ant-pr-review (analysed 2026-10-22). For each one the tables give:
- what we borrowed, and where it lives in this repo (or "planned" when it waits for a later change);
- what we left out, and why.

Licences differ (see each section; two have none and one is share-alike), so ideas are borrowed and paraphrased; no text is copied. None of the eighteen has multi-model review, per-jurisdiction calls, a red-line veto, code-computed verdicts or an ethics guard. Those parts are original to this project. The upstream ant-peer-review references are in that repo's `docs/REFERENCES.md`.

## Repo list

| # | Repo | Kind | Main takeaway |
|---|---|---|---|
| 1 | [coreyhaines31/marketingskills — public-relations @e85f3cb](https://github.com/coreyhaines31/marketingskills/tree/e85f3cbc2e4a79bf33b2a12e9bdd9087d414735b/skills/public-relations) | earned media + crisis comms | channel order, facts first, no premature scope claims |
| 2 | [asgard-ai-platform/skills — pr-social-copywriting @4e7f4f8](https://github.com/asgard-ai-platform/skills/tree/4e7f4f8e389847757a5a4236c2f1ed9813359179/pr-social-copywriting) | social copy per platform | counter-example: inconsistent numbers across channels |
| 3 | [asgard-ai-platform/skills — pr-press-release @4e7f4f8](https://github.com/asgard-ai-platform/skills/tree/4e7f4f8e389847757a5a4236c2f1ed9813359179/pr-press-release) | press release writing (Taiwan) | inverted pyramid, 5W1H lead |
| 4 | [asgard-ai-platform/skills — pr-media-monitoring @4e7f4f8](https://github.com/asgard-ai-platform/skills/tree/4e7f4f8e389847757a5a4236c2f1ed9813359179/pr-media-monitoring) | brand monitoring (Taiwan) | keyword kinds, Taiwan platforms, sensitive periods |
| 5 | [asgard-ai-platform/skills — pr-crisis-response @4e7f4f8](https://github.com/asgard-ai-platform/skills/tree/4e7f4f8e389847757a5a4236c2f1ed9813359179/pr-crisis-response) | crisis protocol + recovery | do not delete, recovery gate, checkable apologies |
| 6 | [asgard-ai-platform/skills — pr-crisis-communication @4e7f4f8](https://github.com/asgard-ai-platform/skills/tree/4e7f4f8e389847757a5a4236c2f1ed9813359179/pr-crisis-communication) | crisis comms, SCCT | posture fit by crisis type and history |
| 7 | [dclacher/pr-crisis-analyzer @eeed137](https://github.com/dclacher/pr-crisis-analyzer/tree/eeed137fb9cb792432dc67f84b443c69c58fa0af) | tweet-reply tone prototype | counter-example: sentiment is not a crisis signal |
| 8 | [metadatastician/sim-public-relations @c4db8ff](https://github.com/metadatastician/sim-public-relations/tree/c4db8ffb9afbbdbe125a1ff91ad2312ceb863189) | fictional PR practice simulator (UK) | critical errors are never averaged; staged launch; simulation labelled |
| 9 | [tsy-fred/declaration-and-media-skill @a4ea626](https://github.com/tsy-fred/declaration-and-media-skill/tree/a4ea626a81fc90e41072e13f833e0ae6f8da8152) | statements and media handling (mainland China, NGOs) | four-part statement; no positive content during the outbreak |
| 10 | [AshLSnow/pr-crisis @349f344](https://github.com/AshLSnow/pr-crisis/tree/349f34486ca3ce3d80ccc5ab6f81259b748664b0) | harm × spread triage, case library | not everything is a rumour; stop harm first; graded sources |
| 11 | [ur-grue/autopunk-media-skills — pr-communications @39e119b](https://github.com/ur-grue/autopunk-media-skills/tree/39e119bfef25957223d6c44fccab0329e936d2f6/skills/pr-communications) | crisis package and media-relations skills | holding statement, landmines, embargo agreement, disclosure first |
| 12 | [ShenyuanNext/wepr-growth-skills — wepr-human-writing @822504b](https://github.com/ShenyuanNext/wepr-growth-skills/tree/822504b8c72003b7efe84cb5c621bf752a3244fe/skills/wepr-human-writing) | natural-Chinese rewriting | no simulated quotes; headline within the facts; counter-example: model-tell scrubbing |
| 13 | [ShenyuanNext/wepr-growth-skills — wepr-editorial-quality @822504b](https://github.com/ShenyuanNext/wepr-growth-skills/tree/822504b8c72003b7efe84cb5c621bf752a3244fe/skills/wepr-editorial-quality) | editorial audit, minimal rewrite | protected details; never claim a text is AI-written |
| 14 | [ShenyuanNext/wepr-growth-skills — draft-corporate-content-appeals @822504b](https://github.com/ShenyuanNext/wepr-growth-skills/tree/822504b8c72003b7efe84cb5c621bf752a3244fe/skills/draft-corporate-content-appeals) | takedown appeals (mainland China) | an evidence bar for strong labels; the right route per right |
| 15 | [ShenyuanNext/wepr-growth-skills — pr-strategy-workbench @822504b](https://github.com/ShenyuanNext/wepr-growth-skills/tree/822504b8c72003b7efe84cb5c621bf752a3244fe/skills/pr-strategy-workbench) | PR strategy and copy review | can the organisation honour it; option ladder; intent is a hypothesis |
| 16 | [ShenyuanNext/wepr-growth-skills — diagnose-pr-crisis @822504b](https://github.com/ShenyuanNext/wepr-growth-skills/tree/822504b8c72003b7efe84cb5c621bf752a3244fe/skills/diagnose-pr-crisis) | crisis diagnosis | one objective per message; issue states; no golden hours |
| 17 | [ShenyuanNext/wepr-growth-skills — analyze-brand-strategy @822504b](https://github.com/ShenyuanNext/wepr-growth-skills/tree/822504b8c72003b7efe84cb5c621bf752a3244fe/skills/analyze-brand-strategy) | brand positioning | a claim is not a fact; not found is not absent; five competitor roles |
| 18 | [ShenyuanNext/wepr-growth-skills — wepr-market-signal-research @822504b](https://github.com/ShenyuanNext/wepr-growth-skills/tree/822504b8c72003b7efe84cb5c621bf752a3244fe/skills/wepr-market-signal-research) | public-signal research | reposts are one source; engagement never summed |

Full commits read: coreyhaines31/marketingskills `e85f3cbc2e4a79bf33b2a12e9bdd9087d414735b`; asgard-ai-platform/skills `4e7f4f8e389847757a5a4236c2f1ed9813359179`; dclacher/pr-crisis-analyzer `eeed137fb9cb792432dc67f84b443c69c58fa0af`; metadatastician/sim-public-relations `c4db8ffb9afbbdbe125a1ff91ad2312ceb863189`; tsy-fred/declaration-and-media-skill `a4ea626a81fc90e41072e13f833e0ae6f8da8152`; AshLSnow/pr-crisis `349f34486ca3ce3d80ccc5ab6f81259b748664b0`; ur-grue/autopunk-media-skills `39e119bfef25957223d6c44fccab0329e936d2f6`; ShenyuanNext/wepr-growth-skills `822504b8c72003b7efe84cb5c621bf752a3244fe`.

Licences: #1-6 MIT (root LICENSE at the commit read); #7 none; #8 code MPL-2.0, documents CC-BY-SA-4.0; #9 no licence file (its README says MIT); #10 MIT, concept from a paid column; #11 MIT; #12-18 MIT (an agency's marketing suite, scwepr.com).

## 1. coreyhaines31 public-relations (@e85f3cb)

| Borrowed | Where here |
|---|---|
| Channel order: affected parties first, staff no later than the public, press never before the affected | `schemas.TIMELINE` step `audience`; `timeline.build` warns (S-plans-029) |
| "No sensitive data was affected" is the statement most often walked back | checklist JOU-06 |
| Tell affected people what to do now; set the next update time, promise no fix time | checklist SOC-07, JOU-08 |
| Staff hear it before or with the public | checklist INT-04 |
| The enemy is a system, never a named competitor | checklist EXP-04 (posture expose) |
| Facts first: confirmed vs rumour, who is affected, what is public | planned: drafting-mode fixed questions |
| Tier 4 (breach, injury, lawsuit, regulator): counsel first, holding statement only | planned: drafting mode |
| Track every promise; watch for a second wave | planned: report promise tracker |

| Left out | Why |
|---|---|
| Story angles, outlet lists, pitch templates, AI-citation metrics | Marketing, US-centric and quick to age; outside a risk review. |
| Newsworthiness weights and decay windows | Unsourced numbers. |
| Guessing journalists' emails; a browser session with "no rate limits" | Personal data, and crawling against D-PR-15. |

## 2. asgard pr-social-copywriting (@4e7f4f8)

| Borrowed | Where here |
|---|---|
| Its own sample gives different figures per platform for the same claim (a counter-example) | checklist JOU-07 |

| Left out | Why |
|---|---|
| Hooks, CTAs, hashtags, posting windows, visual specs | Copywriting craft, not risk; unsourced figures ("4x more engagement"). |
| The sample asks beta users to post on launch day without disclosure | A LEG-03 risk, not a practice to copy. |

## 3. asgard pr-press-release (@4e7f4f8)

| Borrowed | Where here |
|---|---|
| Inverted pyramid; the lead paragraph stands alone with 5W1H; quotes add insight | planned: drafting-mode structure check and fixed questions |
| Write the Chinese release natively, not as a translation | planned: drafting-mode language rule |

| Left out | Why |
|---|---|
| Wire costs, coverage-rate baselines, Tue–Thu timing as a rule | Unsourced and quick to age. |
| A sample quote invented for a real, named investor; unsourced market figures | Fabrication about a real person (LEG-01). |

## 4. asgard pr-media-monitoring (@4e7f4f8)

| Borrowed | Where here |
|---|---|
| Keyword kinds: brand, misspellings and homophones, traditional/simplified forms, products, officers, brand + issue terms, exclusions | `schemas.KIT.monitoring_keywords` (term, kind, platforms); handles dropped (S-plans-030) |
| Taiwan platforms beyond the large ones: 巴哈姆特, LINE TODAY, Yahoo 新聞, 靠北 groups | `jurisdictions/tw.toml` platforms |
| Sensitive periods (Lunar New Year, Qingming, the run-up to an election, typhoon season) | not done: lunar and election dates change every year (D-0003, known limit) |

| Left out | Why |
|---|---|
| PTT sentiment formula, "60-70%" spread probabilities | Unsourced heuristics. |
| A political-lean table of named media | Contestable; not ours to assert. |
| Tracking named individual accounts | D-PR-10: we never profile the people behind accounts. |

## 5. asgard pr-crisis-response (@4e7f4f8)

| Borrowed | Where here |
|---|---|
| Do not delete; a necessary removal is acknowledged publicly with its reason | checklist SOC-08 |
| An apology names owners, deadlines and a published follow-up date | checklist APO-03 |
| Employees "helping" on personal accounts | checklist INT-04, ROL-08 |
| Escalation triggers (story published, regulator comments, competitor amplifies, staff posting) | prompts for plan C's escalation tree; stakeholder matrix (STK-*) |
| Recovery readiness gate before any "we're back" or CSR push | planned: timeline trigger rule |

| Left out | Why |
|---|---|
| A PTT reply through a registered account, "risky if identified" | Treats astroturfing as a detection risk (D-PR-7). |
| Ignore accounts that look like bots (no history, generic avatar) | Account profiling (D-PR-10). |
| V×(S+Src) risk score; a US-vs-Taiwan apology generalisation | Unsourced; APO-02 handles liability per jurisdiction. |

## 6. asgard pr-crisis-communication (@4e7f4f8)

| Borrowed | Where here |
|---|---|
| SCCT clusters (victim, accidental, preventable), plus the intensifiers it omits (crisis history, prior reputation) from Coombs (2007), *Corporate Reputation Review* 10(3), 163–176 | checklist JOU-09 |
| Preserve the original source before acting | checklist RSP-04, RBT-02 |
| Pause paid media in a crisis | `timeline.build` warns on a paid step with no stop condition (S-plans-029) |
| Contradictory messages across platforms | checklist JOU-07 |

| Left out | Why |
|---|---|
| A "72-hour notification" stated as general | GDPR Art. 33 only; deadlines come from the packs and counsel. |
| Growth-rate escalation thresholds | Unsourced. |
| "Hide quietly" for abusive comments | Contradicts its own warning; see SOC-08. |

## 7. dclacher pr-crisis-analyzer (@eeed137)

No licence: ideas only.

| Borrowed | Where here |
|---|---|
| Nothing | — |

| Left out | Why |
|---|---|
| Tone scores of one account's replies as crisis detection | Sentiment is not public support; account-level monitoring (D-PR-10). |
| "Attacked by internet trolls" | Claimed, not implemented; account profiling (D-PR-10). |

## 8. metadatastician sim-public-relations (@c4db8ff)

Code MPL-2.0, documents CC-BY-SA-4.0: ideas only, paraphrased.

| Borrowed | Where here |
|---|---|
| Views heard are not endorsement; a forecast restated as a result | checklist JOU-10 |
| Stage the launch: hold earned outreach until claims are resolved | `timeline.build` warns on the first public step while claims are unverified (S-plans-033) |
| Everything a simulation produces is labelled as such | the stakeholder matrix's reaction column is "model-simulated" |
| AI use is declared, never turned into evidence | checklist REG-05 |
| Accessible summary | checklist SOC-09 |
| Critical errors cannot be averaged away; each route records evidence, uncertainty, alternatives, reason, approval | planned: drafting mode |
| Source registry: URL, access date, locator, review status | planned: company profile lookup |

| Left out | Why |
|---|---|
| Competency rubric and learner scoring | A training simulator, not a risk review. |
| The UK reference pack | Provisional and unreviewed; outside tw/us/eu/cn. |

## 9. tsy-fred declaration-and-media-skill (@a4ea626)

No licence file (the README says MIT): ideas only.

| Borrowed | Where here |
|---|---|
| In the outbreak phase handle only the problem; no positive content | `timeline.build` warns on a promotional step before the affected are helped (S-plans-031) |
| Sample invalid statement: "pure rumour, we reserve the right to sue" | checklist JOU-11 (counter-example) |
| Plain words, no jargon | checklist SOC-09 |
| Kuaishou and WeChat Channels | `jurisdictions/cn.toml` platforms |
| Four parts: facts, stance, preliminary cause, measures; accident vs fault | planned: drafting-mode structure |

| Left out | Why |
|---|---|
| "Publish within 5 hours"; a fixed 24-hour to 2-month opinion cycle | Unsourced numbers. |
| Emotional responses carried by opinion leaders | Gray, or black when undisclosed (D-PR-7). |
| Monitoring named accounts; riding trending topics | D-PR-10; PRO-02 risk. |
| Real third-party notices copied in | Third-party text. |

## 10. AshLSnow pr-crisis (@349f344)

MIT, but the concept is from a paid column: ideas only.

| Borrowed | Where here |
|---|---|
| Split mixed allegations by kind; never call all criticism a rumour | checklist JOU-11 |
| Harm × spread sets response intensity; low spread is no excuse when we bear responsibility | checklist RSP-05 |
| No early scapegoat (temp worker, franchisee, supplier, hacked account) | checklist JOU-06 |
| Protect people before repairing reputation | `timeline.build` harm-first rule (S-plans-031) |
| Flag contradictions in the answers; list open unknowns before advising | planned: drafting-mode fixed questions |
| Evidence grades A/B/C; at least one A or two independent B sources | planned: company profile lookup |

| Left out | Why |
|---|---|
| Find the source privately and press them | Identifies people behind accounts (D-PR-10). |
| Platform complaints to throttle or delete; media friends to cool coverage | SOC-08; gray means. |
| Joke comebacks, including retract-without-retracting | Deceptive wording. |
| A hypothesis hidden from the user | Conflicts with a transparent report. |

## 11. ur-grue autopunk-media-skills pr-communications (@39e119b)

MIT.

| Borrowed | Where here |
|---|---|
| "We are confident this will not happen again" and "no jobs are at risk" as landmines | checklist JOU-06 |
| A staff memo forbidding comment even on personal accounts (a counter-example) | checklist INT-05 |
| File with the exchange or regulator before the media; an embargo binds only those who agreed | `timeline.build` disclosure-first rule (S-plans-032); timeline prompt |
| Ghostwritten bylines as a disclosure question | checklist LEG-03 |
| Holding statement, hostile FAQ with "we don't know yet", spokesperson landmines | planned: drafting-mode artefacts |

| Left out | Why |
|---|---|
| Bridging lines that dodge the question | Evasion; RTM-02 risk. |
| Releasing ahead of the regulator to own the narrative | A race, not a duty. |
| "$50,120 per violation" | Inflation-adjusted yearly; quick to age. |
| Self-graded LLM eval scores | Not evidence of quality. |

## 12. ShenyuanNext wepr-human-writing (@822504b)

MIT. A rewriting skill aimed at "降低機械感" (less machine-like); only reader-facing advice is borrowed.

| Borrowed | Where here |
|---|---|
| No quote without an authorised source; never simulate an executive speaking | checklist INT-03 (a named person's first person) |
| The headline goes only as far as the facts; a caveat lower down does not save it | checklist JOU-12 |
| Main clause first, verbs not nominalisations, one name per thing, the remove-the-brand test, adjectives become evidence; writing for the ear | planned: drafting-mode writing checks |

| Left out | Why |
|---|---|
| Sentence-length variance, no dashes or colons, lists of "words models favour" | They target machine-authorship tells, not readers: AI-detection evasion (D-PR-7). The ethics guard now flags such advice. |
| Forum and 知乎 voice with fictional first-person samples and a planted "search trace" | Client content passed off as an independent voice (LEG-09, D-PR-7); the guard flags "sound like an ordinary user". |
| Fiction and poetry guidance | Outside a risk review. |

## 13. ShenyuanNext wepr-editorial-quality (@822504b)

MIT.

| Borrowed | Where here |
|---|---|
| Never claim or guess that a text is AI-generated; no "AI probability" | checklist THR-05 |
| Protected details (names, dates, amounts, scope, quotes) checked after an edit | `plans.protected_changes`: plan A's removed and added numbers, amounts and quotes are disclosed (S-plans-034) |
| Reverse check after a rewrite: facts unchanged, views not strengthened | the re-audit (S-plans-019) and the warning above |
| Evidence labels: confirmed, sourced but unchecked, judgement, assumption, gap | planned: drafting-mode claim register |

| Left out | Why |
|---|---|
| "降低 AI 感" as a use case | Detection evasion is not a quality goal (D-PR-7). |

## 14. ShenyuanNext draft-corporate-content-appeals (@822504b)

MIT.

| Borrowed | Where here |
|---|---|
| An evidence bar for "false", "never happened", "malicious", "paid posters"; a denial bounded by the scope checked | checklist LEG-11 |
| Copyright only for copying, trademark only for source confusion; a signed statement within what was checked | checklist REG-06 |
| One real, contemporaneous counterexample defeats "the only one" | checklist LEG-02; planned: company profile lookup (competitor models) |

| Left out | Why |
|---|---|
| A default closing that asserts malice | Contradicts its own evidence bar; LEG-11. |
| "If not removed, throttle and drop it from search" for criticism | Gray means; SOC-08, RBT-02. |
| Asking the platform to check the poster's identity and linked accounts | Identity-seeking (D-PR-10). |
| Success rates "70%–85%" | Unsourced. |

## 15. ShenyuanNext pr-strategy-workbench (@822504b)

MIT.

| Borrowed | Where here |
|---|---|
| Can the organisation honour the message; change the action before the words | checklist INT-06 |
| Option ladder: none, monitor, internal correction, targeted, public; commitment and reversibility of each | checklist RSP-01 |
| Editorial choices, possible effect and intent kept apart; timing or tone does not prove paid placement | checklist THR-05 |
| "Decision required" (publish, revise, delay, respond, monitor, investigate, withdraw, escalate) | planned: drafting-mode fixed questions |
| Claims: safe to say publicly, internal only, not supportable, needs validation | planned: drafting-mode claim register |
| Pre-launch sort: change the action, prepare the answer, monitor | planned: report risk grouping |

| Left out | Why |
|---|---|
| Proposal scope, KPIs, SLAs, 30/60/90 budgets | Agency sales material. |

## 16. ShenyuanNext diagnose-pr-crisis (@822504b)

MIT.

| Borrowed | Where here |
|---|---|
| Never mix clarification, apology, rebuttal and promotion in one message | checklist SOC-10 |
| Insufficient spread evidence is not "no risk" | checklist RSP-05 (already); planned: report issue state |
| State-change triggers (new facts, more affected, a reusable label, cross-platform, institutions, our own reply); no universal golden hours | planned: timeline trigger kinds |

| Left out | Why |
|---|---|
| Fixed 0–2h / 2–24h buckets | Contradicts its own "no golden hours". |
| "Coordinated attack" as a class with no evidence bar | THR-02 asks for signs in the text only. |

## 17. ShenyuanNext analyze-brand-strategy (@822504b)

MIT.

| Borrowed | Where here |
|---|---|
| An official page proves a claim, not a market position; a search result or AI summary is a lead | planned: company profile lookup (source labels) |
| "Not found" is not "does not exist" | planned: company profile lookup (scoped absence) |
| Five competitor roles: direct, indirect, workaround, inaction, mental benchmark | planned: company profile lookup |
| Different slogans are not different strategies; at most three blocking questions | planned: drafting mode |

| Left out | Why |
|---|---|
| Positioning formula, advantage tests, case patterns | Brand strategy, not risk. |

## 18. ShenyuanNext wepr-market-signal-research (@822504b)

MIT.

| Borrowed | Where here |
|---|---|
| A public reaction inferred from too small a sample is an early lead | checklist JOU-10 |
| Reposts, syndication and aggregators count as one source; engagement per platform, never summed | planned: company profile lookup and context scan |

| Left out | Why |
|---|---|
| Author type per sample; usernames left out only "by default" | We never record the people behind accounts (D-PR-10). |
| Mining public language for copy | Marketing, not risk. |
