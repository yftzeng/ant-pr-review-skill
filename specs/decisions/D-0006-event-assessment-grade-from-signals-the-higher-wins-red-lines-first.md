# D-0006 Event assessment: a grade from observed signals, the higher grade wins, red lines first

| | |
|---|---|
| Status | accepted |
| Decided | 2026-10-22 |
| Features | context-card, review-matrix, plans |
| Glossary term | |
| Authority | user, 2026-10-22: "評估報告生成是否包括這幾個部分：危機等級 + 風險預判 + 行動建議 + 預案啟動判定", "是否包括 ~/19-58.jpg 的處理流程", then "開工" on the proposed scope |
| Guard | tests/test_event_assessment.py |
| Migration | a card without `signals` is ungraded and says so; a card without `characterised` reads as not characterised; a timeline step without `stage` or `silence` renders a blank |
| Related | D-0002 (timeline), D-0005 (drafting's characterised), docs/REFERENCES.md #24 |

## Decision

- **Signals on the card**: the user ticks what is observed, never the model. There are four groups.
  - I: nationwide trending, state media attention, a mass boycott, a threat to the company's survival.
  - II: platform trending, several outlets following, values questioned, rumours spreading, clear business harm.
  - III: social spread, self-media following, a surge in complaints, local reputation harm.
  - IV: small spread, scattered reviews.
  - Bottom lines: major safety, major illegality, minors.
- **The grade is computed in code.**
  - The highest group ticked wins ("the higher grade wins").
  - A bottom-line signal, a drafting tier-4 flag for injury, a crime or minors, or any confirmed red line makes it grade I ("red lines first").
  - Nothing ticked: ungraded, and the report says so.
- **Who handles it** follows the grade:
  - I: the top decision makers plus outside advisers;
  - II: group executives;
  - III: company management;
  - IV: the business unit.
- **Activation**: I and II activate the response kit (plan C) now; III puts it on standby with monitoring and the escalation triggers; IV observes; ungraded leaves it to the user.
- **The report opens with an event assessment**:
  - the grade, who handles it and the reasons;
  - the risk outlook from the existing synthesis (verdict, top risk, red lines, the worst headline);
  - the recommended action (verdict and plans) with pass rates on the three control axes (predictability, explicability, influence);
  - the activation, with its basis;
  - whether the facts characterise the event.
- **Characterised** is on the card for an audit; drafting uses its brief. Not characterised gives a kit with a holding statement only. Characterised also gives a formal statement in the kit.
- **Timeline steps** carry the issue-attention stage (Downs). One step may be the silence point: public statements stop while operations and the owners' channel go on.

## Why not the alternative

- A model-assigned grade: unverifiable, and a model cannot see the trending lists.
- An average of signals: a single grade-I signal must not be averaged away.
- Fixed regrade hours: the source gives none; the report says to regrade when the signals change.

## Deliberately not done

- Structured reports per department (R&D, quality, service, IR, legal, brand). They lengthen every intake and are mostly internal material that should not go to a model.
- Judging whether a trending topic is genuine.
