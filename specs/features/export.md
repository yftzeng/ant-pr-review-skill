# Feature: export

The markdown a run writes is the record. A printable A4 PDF and a Word file are
made from it in Python for the people who act on it: the crisis team prints the
sheet, a manager signs the final text. The output is in the run's language, the
PDF carries its own font, and a machine without the optional packages or a CJK font
still gets the markdown with the reason the other two are missing (D-0007).

```gherkin
Feature: export
  @S-export-001
  Scenario: the markdown subset becomes a PDF and a DOCX with the same text
    Given markdown with headings, paragraphs, bullet and numbered lists, check boxes "- [ ]", a table, a quote, a rule, bold text and a blank "〔　　〕"
    When  it is exported
    Then  the PDF is A4 and the text of every heading, paragraph, list item and table cell is found in the PDF's text and in the DOCX's paragraphs and tables (spacing ignored), check boxes show as □ (open) and ■ (done), glyphs every CJK font has, bold markers are gone
    And   a line the subset does not know is kept as a paragraph, never dropped

  @S-export-002
  Scenario: the run's language picks the labels and the font
    Given a zh-TW run, a zh-CN run and an en run with a CJK font on the machine
    When  each exports with a version "v2" and a time
    Then  the header of each page says the confidential label, the version and the time in that language, the footer the page number
    And   the zh-TW PDF embeds a Traditional Chinese face (TC), the zh-CN one a Simplified one (SC), the en one any CJK face found

  @S-export-003
  Scenario: missing packages or no CJK font leave the markdown and say why
    Given the export packages cannot be imported; and, separately, no CJK font is found
    When  a run exports
    Then  the markdown file is still written, no PDF or DOCX is left behind, and the result names the reason: "packages" with the install command, or "font"
    And   with no CJK font but the packages present, the DOCX is still written (Word uses the reader's fonts)

  @S-export-004
  Scenario: the font is found by name, a configured path first
    Given a configured font path, then the common system locations of Linux, macOS and Windows
    When  the font is chosen
    Then  a configured path that exists wins; otherwise the first known CJK file is opened and the face inside a collection is picked by its family name for the language, never by a fixed index

  @S-export-005
  Scenario: --export writes PDF and DOCX beside the final text of an audit or a drafting run
    Given a drafting run whose 10-final.md is written, or an audit decided with a final.md
    When  the run was started with --export
    Then  10-final.pdf and 10-final.docx (or final.pdf and final.docx) are written next to it with the header and a sign-off box, and the markdown file itself is unchanged
    And   without --export no PDF or DOCX is written
```

## Must NOT
- @N-export-001 A publishable markdown file (final.md, 10-final.md) never gets the header, the version or the sign-off box written into it; they exist only in the PDF and DOCX.
- @N-export-002 An export failure never stops the run or removes the markdown.

## Revisions
- 2026-10-30 · created · decision: none -- no feature turns a run's markdown into a printable file; report and decision write markdown only
- 2026-10-30 · +S-export-001..005, +N-export-001..002 markdown first, PDF and DOCX in Python, the run's language and font (user: PDF 還需依賴太多軟體，考慮先生成 markdown 然後額外提供用 python 轉成的 pdf 及 docx，output 同語系選擇生成對應的語言) · decision: D-0007
