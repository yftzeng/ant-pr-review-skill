# D-0007 Crisis mode: no questions after the event, a shared crisis core, markdown first with PDF and DOCX exports

| | |
|---|---|
| Status | accepted |
| Decided | 2026-10-30 |
| Features | export, context-card, drafting, plans, checklist, menus |
| Glossary term | |
| Authority | user, 2026-10-30: "就用 crisis，然後放在第一個 … 選 crisis 時不會再問用戶任何問題，直接生成 printable a4 pdf，含所有相關素材"; "PDF 還需依賴太多軟體，考慮先生成 markdown 然後額外提供用 python 轉成的 pdf 及 docx，output 同語系選擇生成對應的語言"; "之前列的內容，也請一併考慮摘出值得的部分，合併至 audit 及 drafting"; then "開工" on the proposed four-step order |
| Guard | tests/test_export.py, tests/test_crisis_core.py, tests/test_crisis.py |
| Migration | a card or brief without the three times reads them as not given; a kit without the structured holding statement renders the old single text; a run made before the crisis phase existed marks it done (added later); `--purpose` still defaults to audit |
| Related | D-0005 (drafting), D-0006 (event assessment, characterised), D-0002 (timeline), docs/REFERENCES.md |

## Decision

- **A third purpose, `crisis`, first in the menu.** After it is chosen the only input is the event itself: pasted text, files or links. Nothing else is asked. The defaults are fixed:
  - not characterised, so a holding statement only;
  - white means only;
  - the configured jurisdictions and models, else Taiwan and the first model;
  - no web search;
  - every unknown becomes a blank to fill in on the printed sheet.
- **The CLI default stays `audit`**, so scripts that do not pass `--purpose` keep their behaviour.
- **A crisis run** reads its sources, makes a few calls with one model and writes `crisis.md`, then `crisis.pdf` and `crisis.docx` beside it. The calls are: the fact sheet and grade, the response kit, the operational periods and the other side's case.
  - Its fixed parts are made in code, never by a model: the team roles, the first 30 minutes, the five questions for the business head, the legal checklist, the update log and the sign-off.
  - It hands off: the formal statement goes to `drafting` once the facts characterise the event, and the holding statement can be reviewed by `audit`.
- **The shared core goes into audit and drafting where it applies, never as a mandatory first stage**:
  - the three times (it happened, we first knew, it became public) on the card and in the brief;
  - unknown facts with an owner role and a due time;
  - the structured holding statement and its channel versions;
  - the order of audiences (affected, staff, regulators and partners, press);
  - pausing promotions at grade III or higher;
  - new checklist items: the business-head questions, knowing versus reporting deadlines, frontline wording, press-conference handling;
  - a frontline Q&A;
  - a worst-case scope the statement must not promise beyond.
- **Markdown is the record; PDF and DOCX are made from it in Python** (fpdf2, python-docx, an optional `export` extra). Only a small subset of markdown is read: headings, paragraphs, lists, check boxes, tables, quotes and rules.
  - The PDF embeds a subset of a CJK font found on the machine. The font is chosen by the run's language: TC for zh-TW, SC for zh-CN.
  - Without the extra or a font, the markdown is still written and the reason is shown.
  - Audit and drafting export their final text only with `--export`.
- **The output language is the run's language**: fixed labels come from the locale files, and the model writes in the same language.
- **The version, time and sign-off** go in the PDF and DOCX header and footer and in the crisis sheet. They do not go into a publishable markdown file such as `final.md` or `10-final.md`: a sign-off table there would end up in a published post.

## Why not the alternative

- **The crisis core as a stage before every audit and draft**: most audits are ordinary copy with no event. Running a crisis stage first would cost calls and time and add questions.
- **A browser (Playwright or Chrome) printing HTML to PDF**: too many moving parts on a user's machine. One test run here took 1.3 s with fpdf2 for a 16 KB A4 page with a subset CJK font. The extra needs only pip packages.
- **pandoc or WeasyPrint**: both need system binaries or libraries.
- **Shipping a font in the repo**: one CJK weight is about 7 MB. Downloading one at run time adds a supply-chain step to a no-questions mode.
- **Asking for the missing facts in crisis mode**: the user asked for no questions. A printed blank with its owner is faster to fill than a prompt in a terminal.

## Deliberately not done

- No names of victims, staff, whistle-blowers or influencers. The sheet keeps roles and counts; the media list keeps outlet names and deadlines only. Minors are a yes or no flag.
- A 40/20/40 split of the formal statement is a writing hint, never a rule; it has no evidence behind it.
- No one-way press-conference exit and no cut-off of questions: the length is announced, and the core questions are answered before leaving.
- A rumour is marked false only with a counter-evidence entry; without one it stays unverified.
- Grey and black means are never used in crisis mode, since nobody was asked.
