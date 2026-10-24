"""Stable paragraph / sentence ids: D<doc>.P<nn>.S<n>.

Headings are their own paragraph without sentence ids. The prompt view wraps
every sentence with its id so reviewers can anchor findings precisely.
"""
from __future__ import annotations

import re
import unicodedata

_SENT = re.compile(r"(?<=[。！？!?；;])\s*|(?<=[.])\s+(?=[A-Z0-9\"'“‘(（一-鿿])")


def split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENT.split(text) if s and s.strip()]
    return parts or [text.strip()]


_END = re.compile(r"[。！？!?.;；:：]$")
_STARTS_BLOCK = re.compile(r"(?:#|[-*+•✓]\s|\d+[.)]\s)")
_CJK = re.compile(r"[㐀-鿿]")


def _short(line: str) -> bool:
    return len(_CJK.findall(line)) < 25 if _CJK.search(line) else len(line) < 50


def _join(a: str, b: str) -> str:
    return a + b if _CJK.match(a[-1]) and _CJK.match(b[0]) else f"{a} {b}"


def _blocks(markdown: str) -> list[str]:
    """Blank lines separate blocks. A single line break ends one too, unless the line is
    long, does not end a sentence and the next line does not start a list item or a
    heading: then it is wrapped prose and joins the next (S-source-acquisition-044)."""
    blocks, cur = [], ""
    for line in markdown.splitlines():
        line = " ".join(line.split())
        if not line:
            if cur:
                blocks.append(cur)
            cur = ""
        elif cur and not (_END.search(cur) or _short(cur) or _STARTS_BLOCK.match(line)
                          or cur.startswith("#")):
            cur = _join(cur, line)
        else:
            if cur:
                blocks.append(cur)
            cur = line
    if cur:
        blocks.append(cur)
    return blocks


def segment(markdown: str, doc: int) -> list[dict]:
    """Return [{"id", "kind": "heading"|"para", "text", "sentences": [{"id","text"}]}]."""
    out = []
    for i, block in enumerate(_blocks(markdown), 1):
        pid = f"D{doc}.P{i:02d}"
        if block.startswith("#"):
            out.append({"id": pid, "kind": "heading", "text": block, "sentences": []})
            continue
        sents = [{"id": f"{pid}.S{j}", "text": s}
                 for j, s in enumerate(split_sentences(block), 1)]
        out.append({"id": pid, "kind": "para", "text": block, "sentences": sents})
    return out


def all_ids(segs: list[dict]) -> list[str]:
    ids = []
    for s in segs:
        if s["kind"] == "heading":
            ids.append(s["id"])
        else:
            ids.extend(x["id"] for x in s["sentences"])
    return ids


def prompt_view(segs: list[dict], withheld: dict[str, str] | None = None) -> str:
    """Render segments for a prompt. Paragraph ids in `withheld` map to a flag id
    and are replaced by a marker instead of their text."""
    withheld = withheld or {}
    lines = []
    for s in segs:
        if s["id"] in withheld:
            lines.append(f"[{s['id']}] ⟨withheld: flagged as possible prompt injection "
                         f"{withheld[s['id']]}⟩")
        elif s["kind"] == "heading":
            lines.append(f"[{s['id']}] {s['text']}")
        else:
            lines.append(" ".join(f"[{x['id']}] {x['text']}" for x in s["sentences"]))
    text = "\n\n".join(lines)
    # Strip zero-width / bidi controls; the scan already recorded them.
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
