# D-0005 Drafting mode: a fixed brief, two versions audited by the same matrix, ranked in code

| | |
|---|---|
| Status | accepted |
| Decided | 2026-10-22 |
| Features | drafting |
| Glossary term | |
| Authority | user, 2026-10-22: "(1) 目的 (Radio)：撰寫(Drafting, 生成)或審核(Audit, 既有內容), 預設審核 … 生成需提供至少二個版本，並推薦一個，附上原因"; order "角色＋借鏡檢查題 → 統編 → 撰寫"; answers 固定問答＋可附素材, 2 版，同姿態不同做法, 擋下匯出，報告照樣產生; earlier 程式排序＋模型寫理由 |
| Guard | tests/test_drafting.py |
| Migration | an intake without `purpose` reads as audit; runs created earlier read the new draft phase as done (Run.state) |
| Related | D-PR-14 (reversed in place), D-PR-7 (ethics guard), D-0002 (posture, re-audit), D-0003 (roles), docs/REFERENCES.md #1, #3, #8, #9, #11-#13, #15, #16, #19, #22, #23 |

## Decision

- **Purpose first**: a radio, audit (default) or drafting. Drafting is always outbound.
- **A fixed brief** replaces the targets: facts confirmed, alleged and unknown (numbered C1.., A1.., U1..), the crisis kind, the affected people and their strongest emotion, the outcome wanted, the decision required (publish, revise, delay, respond, monitor, investigate, withdraw, escalate), earlier statements, actions done / in progress / planned, approvers, and tier-4 flags (injury, data breach, lawsuit, regulator, criminal, minors). Material may be attached; it is read like a target, but only to check facts.
- **Stop and ask in code**: an exposé with no confirmed fact pauses before any call. The writer may return blocking questions: at most three are kept; an interactive run asks them and drafts once more; a non-interactive run lists them as open.
- **Tier 4**: any flag makes the versions holding statements, and the report says counsel and the approvers sign off first.
- **Two versions** from one writer, differing in approach under the chosen posture. Versions sharing an approach or at least 80% alike are retried once with the reason; still alike, the second is dropped and disclosed. Every version passes the ethics guard (D-PR-7).
- **Claim register**, enforced in code: a claim may be public only with a confirmed fact as its basis; otherwise it needs validation. A version whose text contains a claim marked not supportable is disqualified.
- **Checks in code**: placeholders and internal notes; W1-W8 (sentence and paragraph length, the four-part structure for apologies and rebuttals, officialese, vague time, nominalisation, the lead's 5W1H, unsupported superlatives). These are readability and accountability checks, never detection evasion.
- **Every stage is reviewed by another model**: the drafts against the brief; each version by the same matrix in its own folder (round 1, provisional, like the re-audit).
- **Ranking**: code orders by disqualification, verdict, top score and pass rate. A model writes the reason; a reason without a number is replaced by one written in code. When every version is disqualified the run pauses.
- **The recommended version** (interactively another may be picked) becomes the run's source, so the full review, plans (diff and revised full text) and the report follow.
- **Export gate**: the ready-to-publish file `10-final.md` is written only when the final text (plan A's revision, else the chosen version) has no placeholder, no internal note (the ethics guard's marker included), no claim still needing validation and no figure absent from both the chosen version and the brief, and the verdict is neither escalate nor no_go. Otherwise any earlier export is removed; the report is always written and lists what blocks. A version no reviewer answered is disqualified.
- **Examples**: patterns and counters from the user's notes, organisations only, ~~short quotes~~ paraphrased lessons with no quote of the source (2026-10-22, after the licence check: the sources are not openly licensed), unverified, at most six per posture in the prompt.

## Why not the alternative

- One version: nothing to compare and no reason to give.
- The model choosing the recommendation: unverifiable and easy to sway; code ranks on the audit's numbers.
- Drafting outside the matrix: the draft would skip the review it exists to pass.
- A version in another posture: it would leave the posture the user chose.
- Warning only on placeholders: an unsourced fact could still be published.

## Deliberately not done

- The promise tracker, timeline trigger kinds and the follow-up rule: planned.
- Choosing the facts for the user: unknowns stay unknown.

## Why a new record

D-PR-14 dropped drafting; reversing it needs its own rules for briefs, claims, ranking and export, which no record covers
