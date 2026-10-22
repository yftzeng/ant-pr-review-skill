# D-0003 Our role and the stakeholder map

| | |
|---|---|
| Status | accepted |
| Decided | 2026-10-22 |
| Features | context-card, checklist, review-matrix, plans |
| Glossary term | |
| Authority | user, 2026-10-22: a "你的角色" step between purpose and posture: a standpoint (涉事方/責任方 default, 受害方/當事方, 關係方), then reasonable combinations with the listed parties (e.g. 涉事方-公司); the checklist covers how each party faces and handles it. Answers: "6 大類檢查題＋反應矩陣", "是我方身分", "角色＋借鏡檢查題 → 統編 → 撰寫" |
| Guard | tests/test_roles.py |
| Migration | an intake without roles reads as responsible:organization; the earlier card stakeholders map onto the new types |
| Related | D-0002 (posture, means); docs/REFERENCES.md (the borrowed items) |

## Decision

- **Standpoint** (checkbox, at least one): responsible (default), affected, related.
- **Identity** (checkbox, at least one): a reasonable pair of a standpoint and a party type, offered only for the ticked standpoints, e.g. responsible:organization, affected:victims, related:partners. "organization" (the company or brand itself) is added to the user's list.
- **The party types** are in seven groups (organization is an identity only). Each has the core concerns and a simulated viewpoint from the user's definitions (2026-10-22), kept in `parties.toml`:
  - governance: executives, board (with the controlling shareholders), staff, whistleblower, implicated_individual (added from the user's definitions);
  - commerce: victims, bystanders, fans, channel, partners;
  - capital: private_investors, public_investors, lenders;
  - authority: regulators, opposing_counsel;
  - politics: the jurisdiction pack's political parties and organs, each with its side (ruling, opposition, party or state organ, semi-official) and an as-of date; ruling_party and opposition_party where a pack lists none (user, 2026-10-22: 政治與政黨). Parties are institutions, not private people;
  - opinion: media, kol, community_leaders;
  - rivals: competitors, short_activists, astroturf.
- **Political identities**: ruling_party and opposition_party may be our identity, with the election-law items. The Chinese party and state organs (party committees, the Propaganda Department, CAC, SAMR, TAO, ARATS) are assessed as stakeholders only, never as our identity: reviewing their influence work is beyond this tool.
- **astroturf (側翼網軍) is never our identity.** A stored identity is re-validated whenever it is read: an unreasonable or malformed one is dropped and reported. It is assessed only as a stakeholder and a threat. short_activists (職業做空/打假機構) may be our identity, with disclosure and securities checks.
- **Stress tests** (user, 2026-10-22): five role stress tests (RTM-01..05: legal floor, public emotion, internal front, business lifeline, opinion ammunition) and three political ones (POL-01..03: ammunition, polarised trap, sovereign red line). They are checklist items in the stakeholders lens, for outbound and inbound, with their own report section.
- **Checklist**:
  - a new jurisdiction-scoped lens, stakeholders, with one item per group (STK-01..06);
  - items asked only for an identity (ROL-*, by party type);
  - borrowed items, credited in docs/REFERENCES.md: JOU-06..09, SOC-07..08, INT-04, RSP-04, APO-03, EXP-04.
- **Stakeholder matrix**: every model answers every party type in each stakeholders unit, with relevance, likely reaction, what they need, our handling and L×I. A missing type is a gap. The report shows the matrix per jurisdiction: highest relevance, max L×I and each model's reaction.
- **Timeline**: each step names its audience. A press or public step before the first step for affected parties gets a warning, as does a paid step without a stop condition.
- **Plan C monitoring keywords** are objects (term, kind, platforms), never handles of private people.

## Why not the alternative

- 21 separate checklist items: more cost and a longer report for the same coverage the matrix gives per type.
- Asking only for the stakeholders the user ticks: silence about a party nobody ticked is how a crisis surprises. Every type is assessed, and relevance says which matter.
- astroturf as our identity: advising a sockpuppet operator is the black PR this tool refuses (D-PR-7).

## Deliberately not done

- Lunar-calendar and election sensitive periods (they need dates per year). This is a known limit.
- Account-level judgements such as "looks like a bot" (D-PR-10).

## Why a new record

D-0002 covers posture and means; who we are in the event and how each stakeholder reacts is a separate axis with its own ethics limit (astroturf is never our role)
