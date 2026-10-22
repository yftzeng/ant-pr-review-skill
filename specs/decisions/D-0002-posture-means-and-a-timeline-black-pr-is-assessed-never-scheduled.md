# D-0002 Posture, means and a timeline: black PR is assessed, never scheduled

| | |
|---|---|
| Status | accepted |
| Decided | 2026-10-22 |
| Features | context-card, checklist, plans, review-matrix |
| Glossary term | |
| Authority | user, 2026-10-22: posture radio (clarify/apologize/attack/defend, default clarify), means checkbox (white/gray/black, default all); report with ASCII pass rates, diff and full revised text, a timeline of means; answered "評估但不排程", "程式排序＋模型寫理由", "再跑一次 quick 審核", "兩批" |
| Guard | tests/test_posture_means.py |
| Migration | an intake without posture or means reads as clarify and all three means; runs created before the reaudit phase treat it as done (Run.state) |
| Related | DESIGN.md D-PR-7 (ethics guard), D-PR-11 (verdicts in code), D-PR-16 |

## Decision

- The ticked means shape only the report's means (the timeline and the excluded table). Reviewers always judge every item from the white, gray and black angles (user, 2026-10-22: "不會影響檢查項，只會影響最後報告的手段").
- Intake asks a **posture** and the **means** in scope (white, gray, black; default all, at least one). Each posture adds its own checklist items; every posture has a legal item that applies in every direction. The postures (revised by the user, 2026-10-22: "澄清道歉/廣告造勢/狙擊爆料/回應抹黑,預設澄清道歉"):
  - clarify_apologize (default): correct facts, and own a wrong where there is one;
  - promote: advertising, campaigns and hype;
  - expose: our own on-the-record disclosure of a named party's wrongdoing, on evidence we may lawfully use;
  - rebut: answer a smear aimed at us.
  The first postures (clarify, apologize, attack, defend) read as clarify_apologize, clarify_apologize, expose, rebut.
- "Expose" is attributable to us. Leaking through unattributed third parties or media "sources", or with evidence obtained by intrusion or against a confidentiality duty, is a black means.
- Plans add a **timeline** (09-plans/T.md): steps by relative day and local time, numbered in time order, each labelled white or gray, with channel, notes, trigger and stop condition. The writer labels each step and a checker from another vendor labels it again; the stricter label wins.
- A step labelled black by either model never enters the timeline. With black ticked, the report has an **excluded table**: why the tactic is black, the law at stake, how such tactics are usually exposed, what to watch for if someone uses it against us, and the lawful alternative. A step in a means the user did not tick is dropped and disclosed.
- Outbound: the report shows the diff, the full revised text (A), and a **re-audit** of A at depth quick by the same models and jurisdictions (round 1 only, marked provisional), with pass rates before and after. Sentences the user locks are never changed by A: a paragraph change that loses a locked sentence is dropped and disclosed.
- The report shows an ASCII pass-rate bar per checklist item: pass / (answers − na). Unanswered items are counted beside the bar, never as passes. It also shows subtotals per lens and scope, and an overall rate.
- Every stage's output is reviewed by a model from another vendor when the roster has one (user, 2026-10-22: "每個階段的產出都要另一個 model 審"): A and B against the risks, C against the risks, the timeline by labelling every step again, the excluded table by flagging entries that read as operational. A flagged entry keeps its tactic, law and alternative, and its exposure and watch-for text are withheld. The report lists each stage with its writer, reviewer and result. A failed review is shown as "not reviewed".
- The report's checklist is a checkbox list (user: "報告裡的勾選清單"). An item is ticked when every answer is pass or na. Each line carries its bar and every reviewer's mark.
- The report phase now runs after plans and the re-audit, so one report carries them.

## Why not the alternative

- Scheduling black steps when the user ticks black: that turns the review into an execution plan for deception, which D-PR-7 forbids.
- Trusting the writer's own label: a writer can call a persona campaign "community outreach". A second model from another vendor, with the stricter label winning, plus the ethics guard on every field, is the check.
- Re-auditing at the original depth: twice the cost for a check whose purpose is "did the revision fix it". Quick covers the same items.

## Deliberately not done

- "How it is exposed" stays at news-report level. No steps, and never how to avoid detection (the guard's evasion scan runs on every field of the excluded table).
- Naming a black tactic in the excluded table is allowed: persona patterns are not scanned in the tactic and why fields there, only in the lawful alternative. Evasion patterns are scanned everywhere.
- Drafting mode (batch 2) is not part of this record.

## Why a new record

D-PR-7 covers the ethics guard for plans but not the choice of means or a schedule of actions; D-PR-14 dropped drafting, and this adds a posture, a means filter, a timeline and a re-audit of the revision
