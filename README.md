# ant-pr-review

Multi-model, multi-vendor **public-relations risk review**, shipped as a Claude skill (`SKILL.md`) plus a standalone Python CLI. [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md)

It reviews three kinds of material:
- **outbound**: content you plan to publish (press release, statement, post, ad, KOL script);
- **operation**: a dissemination or influence plan;
- **inbound**: hostile content aimed at you (allegation, smear, review wave).

For each, it shows the white-PR and black-PR risks per jurisdiction: Taiwan, United States, European Union, China.

- **A checklist every model answers.** fixed items across 10 lenses (plus items per posture and per role): legal, hostile journalist, online communities, named party, regulators and platforms, insiders, whistleblower, threat analyst, response adviser. An unanswered item is a gap, never a pass.
- **Many vendors.** Claude (opus / sonnet / fable via `claude -p`), OpenAI, Gemini, Grok and OpenRouter, picked with an arrow-key checkbox. A single-vendor roster is allowed but highlighted, because same-vendor models share blind spots.
- **One jurisdiction per call.** Each jurisdiction is reviewed by its own calls. With several jurisdictions, an independent merger compares the results, asks each jurisdiction's reviewers questions, and writes a consolidated report plus one report per jurisdiction.
- **Two depths.** `quick` makes one call per model plus one per jurisdiction; `full` makes one call per lens and jurisdiction (about 4× the calls).
- **Verdicts by code.** A risk register (likelihood × impact), red-line vetoes (fabrication about a named party, sockpuppets and undisclosed endorsement, doxxing, election law, market manipulation, health claims, hate) and Go / Conditional / Escalate / No-Go.
- **Plans A/B/C behind an ethics guard.** A is the smallest safe edit (char-level diff), B the lawful alternative, C the response kit. The guard removes advice to hide attribution, persona comments and laundered allegations, and says what it removed.
- **Posture and means.** Pick a posture (clarify/apologize, promote, expose, rebut a smear; each adds its own checklist items; an exposé is on the record, never leaked through unattributed third parties) and the means the plan may use (white, gray, black). Reviewers always judge every item from all three angles. The report then gives a timeline of white and gray steps (relative day, local time, order, channel, notes, trigger and stop), labelled again by a model from another vendor. Black PR is never scheduled: it is assessed in an excluded table (law at stake, how it is exposed, what to watch for, lawful alternative).
- **Company profile.** Give the Taiwan tax ID (統一編號) and, with your consent, the registry is read for the company's facts and business items (never the representative's name or address), and a search model proposes competitors. Each competitor's sources are graded A/B/C and only those you tick enter the review.
- **Our role and the stakeholder map.** Say who you are in the event (responsible, affected or related, then e.g. the company itself, the board, an endorser, a whistleblower), and the checklist adds items for that role. Every model answers how each party in seven groups (governance, business chain, capital markets, authorities, politics and parties, opinion, rivals) will react, what they need and how to handle them, per jurisdiction. Sockpuppet networks and Chinese party or state organs are assessed, never offered as a role. Five role stress tests (legal floor, public emotion, internal front, business lifeline, opinion ammunition) and three political ones (ammunition, polarised trap, sovereign red line) quote the sentence that would fail.
- **Every stage reviewed, every item a checkbox.** A, B, C, the timeline and the excluded table are each reviewed by a model from another vendor. The checklist is a checkbox list with an ASCII pass-rate bar and every reviewer's verdict. For outbound content the report also shows the diff and the full revised text, and the revision is re-audited at quick depth (before → after). Sentences you lock are never changed.
- **Crisis mode.** When something has just happened, choose `crisis` (first in the menu), paste what you have, and nothing else is asked. You get a printable response sheet for the first hours in your language, as markdown with an A4 PDF and a Word file beside it: the bottom line, team roles, the first 30 minutes, a fact sheet with who checks each unknown by when, the holding statement in six parts with versions for each channel, Q&A, a timeline, who to tell in what order, a legal checklist for counsel, questions for the business head, the other side's case, the gray and black tactics the other side may use (astroturfing, intrusion, anonymous letters, false flags) and how to defend against them, press-conference preparation, an update log and a sign-off. Every unknown is a blank to fill in by hand; nobody is named.
- **Drafting mode.** Instead of auditing, answer a fixed brief (facts confirmed, alleged and unknown; the kind of matter; who is affected and their strongest emotion; the outcome and the decision required; actions and their status; approvers; whether the cause and scope are confirmed, holding statements only until they are; what the statement must not concede or promise; tier-4 flags such as injury or a lawsuit) and optionally attach material to check facts against. One model writes two versions that differ in approach, another reviews them against the brief, and each is audited by the same checklist matrix. Code ranks them (disqualification, verdict, top score, pass rate), a model explains the ranking with the numbers, and the recommended version goes through the full review, ending with its diff and revised full text. Every claim is registered as public, internal only, not supportable or needing validation; a gap stays `[待查證]`, and the ready-to-publish `10-final.md` is written only when no placeholder, internal note or line we cannot commit to remains.
- **Event assessment.** Tick what you have observed (trending, media following, complaints, a safety bottom line…). The report opens with a crisis grade I–IV computed in code (the higher grade wins; safety, illegality, minors or a confirmed red line give grade I), who handles it, the risk outlook, the recommended action with pass rates on predictability, explicability and influence, and whether the response kit is activated now, on standby or not at all.
- **Embargo mode.** Nothing reaches the web for unreleased material. Context-scan queries are shown and need your consent.

Not legal advice. The law packs in `src/ant_pr_review/jurisdictions/` are unverified starting lists. Every law citation a model relies on is fact-checked.

## Install

```
uv tool install .        # or: pipx install .
ant-pr-review            # interactive
```

Printable PDF and Word copies: `uv tool install '.[export]'` (fpdf2, python-docx) and a CJK font on the machine; set `ANT_PR_REVIEW_FONT` to a .ttf, .otf or .ttc file if none is found.

JavaScript-rendered pages: `uv tool install '.[render]'` and `playwright install chromium`. A failed fetch falls back to retries with backoff, then the headless browser, then the AMP version, then a dated Wayback Machine copy, and finally asks you to paste the text. The crawler never disguises itself as a browser.

Python 3.11+. You need the `claude` CLI for Claude models, and keys for the other vendors: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, `OPENROUTER_API_KEY`. No runtime dependencies.

## Non-interactive

```
ant-pr-review new --yes --direction outbound --jurisdictions tw,us --depth full \
  --party "Competitor A" --embargo --target ./release.md
ant-pr-review decide <run> --yes --choice A
ant-pr-review new --yes --purpose crisis --target ./what-we-know.md   # crisis sheet
ant-pr-review new --yes --brief ./brief.toml --target ./internal-notes.md   # drafting
```

Try it offline with `--backend fake`. Design: `docs/DESIGN.md`; reference skills: `docs/REFERENCES.md`. Evaluation of the ant-peer-review fork: `docs/EVALUATION.md`.
