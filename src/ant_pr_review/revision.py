"""Text-edit helpers for plans: apply paragraph/sentence changes, char-level (CJK safe) diffs."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from .jsonio import read_json
from .workspace import Run


def char_diff(old: str, new: str) -> str:
    """Inline diff: [-removed-]{+added+}, compared character by character (CJK safe)."""
    out = []
    for op, a1, a2, b1, b2 in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(old[a1:a2])
        if op in ("delete", "replace"):
            out.append(f"[-{old[a1:a2]}-]")
        if op in ("insert", "replace"):
            out.append(f"{{+{new[b1:b2]}+}}")
    return "".join(out)


def paragraphs(run: Run) -> dict[str, dict]:
    segs = read_json(run.path("01-sources/segments.json"), default={})
    return {s["id"]: s for doc in segs.values() for s in doc}


INSERT = "+"


def render_text(paras: dict[str, dict], replaced: dict[str, str]) -> str:
    out = []
    for pid, s in paras.items():
        out.append(replaced.get(pid, s["text"]))
        if pid + INSERT in replaced:
            out.append(replaced[pid + INSERT])
    return "\n\n".join(out) + "\n"


def _norm_id(raw: str) -> str:
    """Accept 'D1.P03', 'D1.P03.S2', 'D1.P03+', and tolerate 'D1.P03a' / trailing notes."""
    m = re.match(r"\s*(D[\w-]*?\.P\d+)(\.S\d+)?\s*(\+|[a-z]\b)?", raw)
    if not m:
        return raw.strip()
    return m.group(1) + (m.group(2) or "") + (INSERT if m.group(3) else "")


def apply_changes(paras: dict[str, dict], changes: list[dict]) -> tuple[dict[str, str], list[str]]:
    """Map model changes onto paragraphs. Sentence ids replace one sentence;
    'P+' ids insert a paragraph after P (several inserts are joined in order)."""
    replaced, warnings = {}, []
    sentence_edits: dict[str, dict[str, str]] = {}
    for ch in changes:
        cid = _norm_id(ch["id"])
        text = ch["text"].strip()
        pid = ".".join(cid.rstrip(INSERT).split(".")[:2])
        if pid not in paras:
            warnings.append(f"unknown paragraph id from model: {ch['id']}")
        elif cid.endswith(INSERT):
            key = pid + INSERT
            replaced[key] = (replaced[key] + "\n\n" + text) if key in replaced else text
        elif cid.count(".") == 2:
            sids = {s["id"] for s in paras[pid]["sentences"]}
            if cid in sids:
                sentence_edits.setdefault(pid, {})[cid] = text
            else:
                warnings.append(f"unknown sentence id from model: {ch['id']}")
        else:
            replaced[pid] = text
    for pid, edits in sentence_edits.items():
        if pid in replaced:
            continue  # a whole-paragraph rewrite wins over sentence edits
        joiner = "" if re.search(r"[\u3000-\u9fff]", paras[pid]["text"]) else " "
        replaced[pid] = joiner.join(edits.get(s["id"], s["text"])
                                    for s in paras[pid]["sentences"])
    return replaced, warnings


def diff_text(paras: dict[str, dict], replaced: dict[str, str]) -> str:
    blocks = []
    for pid, new in replaced.items():
        old = paras.get(pid, {}).get("text", "")  # "" for an inserted paragraph
        if old == new:
            continue
        block = f"@@ {pid} @@\n- {old}\n+ {new}\n"
        # Inline marks help only for edits; a rewrite reads better as -/+ alone.
        if SequenceMatcher(None, old, new, autojunk=False).ratio() >= 0.5:
            block += f"~ {char_diff(old, new)}\n"
        blocks.append(block)
    return "\n".join(blocks)
