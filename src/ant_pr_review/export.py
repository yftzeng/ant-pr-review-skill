"""Markdown first; a printable A4 PDF and a DOCX made from it in Python (D-0007).

Only the subset the tool writes is read: headings, paragraphs, bullet and numbered
lists, check boxes, tables, quotes and rules; any other line stays a paragraph. The PDF
embeds a subset of a CJK font found on the machine, its face picked by name for the
run's language. Missing packages or font: the markdown stays and the reason is returned.
"""
from __future__ import annotations

import glob
import html
import os
import re
from datetime import datetime
from pathlib import Path

from .i18n import T
from .jsonio import read_json

INSTALL = 'pip install "ant-pr-review[export]"'
FONT_ENV = "ANT_PR_REVIEW_FONT"
# Common CJK font files, most specific first; a glob may match several.
CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/**/NotoSansCJK*-Regular.tt[cf]",
    "/usr/share/fonts/**/NotoSans[TS]C-Regular.[ot]tf",
    "/usr/share/fonts/**/SourceHanSans*-Regular.tt[cf]",
    "/usr/share/fonts/**/wqy-*.ttc",
    "~/.local/share/fonts/**/NotoSans*CJK*.tt[cf]",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/msjh.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/mingliu.ttc",
    "C:/Windows/Fonts/simsun.ttc",
]
# The face a language wants, by words in its family name; the first match wins.
FACES = {"zh-TW": ("TC", "Traditional", "JhengHei", "MingLiU", "PingFang TC", "Heiti TC"),
         "zh-CN": ("SC", "Simplified", "YaHei", "SimSun", "PingFang SC", "Heiti SC")}
DOCX_FONT = {"zh-TW": "Microsoft JhengHei", "zh-CN": "Microsoft YaHei", "en": "Microsoft JhengHei"}


# ---- the markdown subset ------------------------------------------------------------

_LI = re.compile(r"^\s*(?:([-*+])|(\d+)[.)])\s+(?:\[([ xX])\]\s+)?(.*)$")
_ROW = re.compile(r"^\s*\|.*\|\s*$")
_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")


def inline(s: str) -> str:
    """Bold, italic and code markers dropped; a link keeps its text and URL."""
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", s)
    s = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"<!--.*?-->", "", s)
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~])", r"\1", s)  # markdown escapes
    return html.unescape(s).strip()  # report.cell() writes &lt; &gt; &amp;


def _cells(line: str) -> list[str]:
    body = line.strip().strip("|")
    return [inline(c) for c in re.split(r"(?<!\\)\|", body)]


def parse_md(md: str) -> list[tuple]:
    """("h", level, text) ("p", text) ("li", marker, text) ("table", rows) ("quote", text)
    ("hr",). marker: "•", "1.", "□" or "■" (glyphs every CJK font has; ☐ is missing from Noto CJK)."""
    out: list[tuple] = []
    lines = md.splitlines()
    i, para = 0, []

    def flush():
        if para:
            out.append(("p", inline(" ".join(para) if not _cjk_join(para) else "".join(para))))
            para.clear()
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s or re.fullmatch(r"<!--.*?-->", s):
            flush()
        elif m := re.match(r"^(#{1,6})\s+(.*)$", s):
            flush()
            out.append(("h", len(m.group(1)), inline(m.group(2).rstrip("#").strip())))
        elif re.fullmatch(r"(?:-{3,}|\*{3,}|_{3,})", s):
            flush()
            out.append(("hr",))
        elif _ROW.match(line):
            flush()
            rows = []
            while i < len(lines) and (_ROW.match(lines[i]) or _SEP.match(lines[i])):
                if not _SEP.match(lines[i]):
                    rows.append(_cells(lines[i]))
                i += 1
            out.append(("table", rows))
            continue
        elif s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(("quote", inline(" ".join(q for q in quote if q))))
            continue
        elif m := _LI.match(line):
            flush()
            box = m.group(3)
            marker = ("■" if box.lower() == "x" else "□") if box is not None \
                else (f"{m.group(2)}." if m.group(2) else "•")
            out.append(("li", marker, inline(m.group(4))))
        else:
            para.append(s)
        i += 1
    flush()
    return out


def _cjk_join(parts: list[str]) -> bool:
    return any(re.search(r"[\u3000-\u9fff\uff00-\uffef]$", p) for p in parts[:-1])


# ---- the font ------------------------------------------------------------------------

def _faces(path: str) -> list[tuple[int, str]]:
    """(index, family) of each face in a font file or collection."""
    from fontTools.ttLib import TTCollection, TTFont
    try:
        fonts = TTCollection(path, lazy=True).fonts if path.lower().endswith(".ttc") \
            else [TTFont(path, lazy=True)]
    except Exception:  # an unreadable or unsupported file is skipped
        return []
    out = []
    for n, f in enumerate(fonts):
        name = f["name"]
        fam = name.getDebugName(16) or name.getDebugName(1) or ""
        out.append((n, fam))
    return out


def _files() -> list[str]:
    out = []
    for c in CANDIDATES:
        c = os.path.expanduser(c)
        hits = sorted(glob.glob(c, recursive=True)) if any(x in c for x in "*?[") else \
            ([c] if os.path.isfile(c) else [])
        out += [h for h in hits if h not in out]
    return out


def find_font(lang: str) -> dict | None:
    """The configured file first, then the known locations; inside a file the face whose
    family names the language (TC for zh-TW, SC for zh-CN), else the first face."""
    try:
        import fontTools  # noqa: F401  (comes with fpdf2)
    except ImportError:
        return None
    env = os.environ.get(FONT_ENV, "").strip()
    files = ([env] if env and os.path.isfile(env) else []) + _files()
    want = FACES.get(lang, ())
    fallback = None
    for path in files:
        faces = _faces(path)
        for w in want:
            for n, fam in faces:
                if re.search(rf"(?<![A-Za-z]){re.escape(w)}(?![A-Za-z])", fam, re.I):
                    return {"path": path, "index": n, "family": fam}
        if faces and fallback is None:
            fallback = {"path": path, "index": faces[0][0], "family": faces[0][1]}
            if path == env or not want:
                return fallback
    return fallback


# ---- writers ---------------------------------------------------------------------------

def _header(t: T, version: str, when: str) -> str:
    bits = [t("export.confidential")]
    if version:
        bits.append(f"{t('export.version')} {version}")
    if when:
        bits.append(f"{t('export.time')} {when}")
    return " · ".join(bits)


def _signoff_rows(t: T) -> list[list[str]]:
    return [[t("export.signoff.role"), t("export.signoff.sign"), t("export.signoff.date")],
            ["", "", ""], ["", "", ""], ["", "", ""]]


def _write_pdf(blocks, out: Path, t: T, header: str, font: dict, signoff: bool) -> None:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    class Sheet(FPDF):
        def header(self):
            self.set_font("cjk", size=8)
            self.set_text_color(90)
            self.cell(0, 6, header, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_text_color(0)
            self.ln(2)

        def footer(self):
            self.set_y(-12)
            self.set_font("cjk", size=8)
            self.set_text_color(90)
            self.cell(0, 6, t("export.page", n=self.page_no(), total="{nb}"), align="C")
            self.set_text_color(0)

    pdf = Sheet(format="A4")
    pdf.set_margins(18, 15, 18)
    pdf.set_auto_page_break(True, margin=18)
    for style in ("", "B"):
        pdf.add_font("cjk", style=style, fname=font["path"], collection_font_number=font["index"])
    pdf.alias_nb_pages("{nb}")
    pdf.add_page()

    def para(text, size=10.5, h=6, indent=0):
        pdf.set_font("cjk", size=size)
        pdf.set_x(pdf.l_margin + indent)
        pdf.multi_cell(pdf.epw - indent, h, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    def table(rows):
        width = max(len(r) for r in rows)
        pdf.set_font("cjk", size=9.5)
        with pdf.table(line_height=5.5, text_align="LEFT", first_row_as_headings=True) as tb:
            for r in rows:
                row = tb.row()
                for c in r + [""] * (width - len(r)):
                    row.cell(c)
        pdf.ln(2)

    for b in blocks:
        kind = b[0]
        if kind == "h":
            pdf.ln(2)
            para(b[2], size={1: 16, 2: 13, 3: 11.5}.get(b[1], 11), h=8 if b[1] == 1 else 7)
        elif kind == "p":
            para(b[1])
            pdf.ln(1.5)
        elif kind == "li":
            para(f"{b[1]} {b[2]}", indent=4)
        elif kind == "table":
            table(b[1])
        elif kind == "quote":
            pdf.set_text_color(90)
            para(b[1], indent=4)
            pdf.set_text_color(0)
            pdf.ln(1.5)
        elif kind == "hr":
            pdf.ln(1)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)
    if signoff:
        pdf.ln(4)
        para(t("export.signoff"), size=11.5, h=7)
        table(_signoff_rows(t))
    pdf.output(str(out))


def _write_docx(blocks, out: Path, t: T, header: str, lang: str, signoff: bool) -> None:
    import docx
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt

    d = docx.Document()
    sec = d.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.left_margin = sec.right_margin = Mm(18)
    face = DOCX_FONT.get(lang, DOCX_FONT["en"])
    for name in ("Normal", "Heading 1", "Heading 2", "Heading 3", "Quote"):
        st = d.styles[name]
        rpr = st.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.append(fonts)
        fonts.set(qn("w:eastAsia"), face)
    d.styles["Normal"].font.size = Pt(10.5)
    sec.header.paragraphs[0].text = header
    foot = sec.footer.paragraphs[0]
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    foot._p.append(field)

    def table(rows):
        width = max(len(r) for r in rows)
        tb = d.add_table(rows=len(rows), cols=width)
        tb.style = "Table Grid"
        for r, cells in enumerate(rows):
            for c, text in enumerate(cells + [""] * (width - len(cells))):
                tb.cell(r, c).text = text

    for b in blocks:
        kind = b[0]
        if kind == "h":
            d.add_heading(b[2], level=min(b[1], 3))
        elif kind == "p":
            d.add_paragraph(b[1])
        elif kind == "li":
            if b[1] == "•":
                d.add_paragraph(b[2], style="List Bullet")
            else:
                d.add_paragraph(f"{b[1]} {b[2]}")
        elif kind == "table":
            table(b[1])
        elif kind == "quote":
            d.add_paragraph(b[1], style="Quote")
        elif kind == "hr":
            p = d.add_paragraph()
            ppr = p._p.get_or_add_pPr()
            border = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "999999")):
                bottom.set(qn(k), v)
            border.append(bottom)
            ppr.append(border)
    if signoff:
        d.add_heading(t("export.signoff"), level=3)
        table(_signoff_rows(t))
    d.save(str(out))


def _importable(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def export_md(md_path, lang: str, *, version: str = "", when: str = "",
              signoff: bool = False) -> dict:
    """Write <name>.pdf and <name>.docx beside the markdown. Never raises (N-export-002):
    each format is written, or left out with its reason: packages, font or error."""
    md_path = Path(md_path)
    t = T(lang)
    blocks = parse_md(md_path.read_text(encoding="utf-8"))
    header = _header(t, version, when)
    res: dict = {"pdf": None, "docx": None, "reasons": {}, "errors": {}, "install": INSTALL}
    targets = {"pdf": md_path.with_suffix(".pdf"), "docx": md_path.with_suffix(".docx")}
    for fmt, out in targets.items():
        out.unlink(missing_ok=True)  # never leave an earlier copy of another text
        if not _importable("fpdf" if fmt == "pdf" else "docx"):
            res["reasons"][fmt] = "packages"
            continue
        tmp = out.with_name(out.name + ".part")
        try:
            if fmt == "pdf":
                font = find_font(lang)
                if font is None:
                    res["reasons"][fmt] = "font"
                    continue
                res["font"] = font
                _write_pdf(blocks, tmp, t, header, font, signoff)
            else:
                _write_docx(blocks, tmp, t, header, lang, signoff)
            tmp.replace(out)
            res[fmt] = out
        except Exception as e:  # N-export-002: the run goes on with its markdown
            res["reasons"][fmt] = "error"
            res["errors"][fmt] = f"{type(e).__name__}: {e}"[:200]
        finally:
            tmp.unlink(missing_ok=True)
    if not res["errors"]:
        res.pop("errors")
    return res


def notes(t: T, res: dict) -> list[str]:
    """What to tell the user about one export."""
    files = [p.name for p in (res.get("pdf"), res.get("docx")) if p]
    out = [t("export.written", files=", ".join(files))] if files else []
    for fmt, why in res.get("reasons", {}).items():
        out.append(t(f"export.skipped.{why}", fmt=fmt.upper(), install=res["install"],
                     error=res.get("errors", {}).get(fmt, "")))
    return out


def drop_exports(run, rel: str) -> None:
    for ext in (".pdf", ".docx"):
        run.path(rel).with_suffix(ext).unlink(missing_ok=True)


def export_if_asked(run, rel: str) -> dict | None:
    """S-export-005: an audit or drafting run started with --export gets a PDF and DOCX of
    its final text, with the header and a sign-off box; the markdown is not touched."""
    intake = read_json(run.path("00-intake.json"), default={})
    if not intake.get("export"):
        return None
    from .report import latest_version
    v = latest_version(run)
    return export_md(run.path(rel), intake.get("lang") or "en", version=f"v{v}" if v else "",
                     when=datetime.now().strftime("%Y-%m-%d %H:%M"), signoff=True)
