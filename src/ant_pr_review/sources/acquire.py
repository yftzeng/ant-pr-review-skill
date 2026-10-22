"""P4 sources phase: targets -> raw/ + normalized/ + segments.json + injection-scan.json.

Each target is one work item; a resumed phase retries only items not "ok".
Doc ids are fixed by target position (D<i>, or D<i>-<k> for files of a folder),
so retrying one item never renumbers the others.
"""
from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

from ..jsonio import read_json, sha256_bytes, write_json, write_text_atomic
from ..workspace import Run
from .converter import ConvertError, convert_file, convert_folder, pdf_to_markdown
from .crawler import Crawler, FetchError
from .feeds import FEED_TYPES
from .htmlmd import html_to_markdown
from .injection import scan
from .render import RenderError
from .segments import segment

THIN_PAGE_CHARS = 200


def _doc_record(run: Run, doc_id: str, origin: str, title: str, markdown: str,
                raw: bytes, raw_name: str, hidden: list[dict]) -> dict:
    raw_path = run.root / "01-sources" / "raw" / raw_name
    if not raw_path.exists():
        run.write_raw_source(raw_name, raw)
    norm = f"01-sources/normalized/{doc_id}.md"
    header = f"<!-- source: {origin} -->\n\n" if origin else ""
    write_text_atomic(run.path(norm), header + markdown + "\n")
    return {"doc": doc_id, "origin": origin, "title": title, "sha256": sha256_bytes(raw),
            "normalized": norm, "hidden": hidden, "chars": len(markdown)}


# These are a site's or our own refusal: honoured, never worked around (D-PR-15).
NO_FALLBACK = {"robots", "site_profile_blocked", "blocked_address", "scheme",
               "credentials_in_url", "bad_url", "no_host", "is_feed"}
ARCHIVE_API = "https://archive.org/wayback/available?url="
_AMP_RE = re.compile(r"<link\b[^>]*\brel=[\"']?amphtml\b[^>]*>", re.I)
_HREF_RE = re.compile(r"\bhref=[\"']?([^\"'\s>]+)", re.I)


def _convert(res) -> tuple[str, list[dict], str, str]:
    if res.content_type in ("text/html", "application/xhtml+xml"):
        conv = html_to_markdown(res.body.decode("utf-8", "replace"))
        return conv.markdown, conv.hidden, conv.title, "html"
    if res.content_type == "application/pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(res.body)
            f.flush()
            return pdf_to_markdown(Path(f.name)), [], "", "pdf"
    return res.body.decode("utf-8", "replace"), [], "", "txt"


def _amp_url(html: bytes, base: str) -> str | None:
    m = _AMP_RE.search(html.decode("utf-8", "replace"))
    href = _HREF_RE.search(m.group(0)) if m else None
    return urljoin(base, href.group(1)) if href else None


def _rendered(run, crawler, renderer, idx, url, title):
    try:
        html = renderer.render(url, allow=crawler.request_allowed, max_bytes=crawler.max_bytes,
                               timeout=crawler.timeout * 3)
    except RenderError:
        return None
    conv = html_to_markdown(html)
    doc_id = f"D{idx}"
    return {"docs": [_doc_record(run, doc_id, url, conv.title or title, conv.markdown,
                                 html.encode("utf-8"), f"{doc_id}.rendered.html", conv.hidden)],
            "via": "render"}


def _amp(run, crawler, idx, res, title):
    amp = _amp_url(res.body, res.final_url)
    if not amp:
        return None
    try:
        r = crawler.fetch(amp)
    except FetchError:
        return None
    md, hidden, t2, ext = _convert(r)
    doc_id = f"D{idx}"
    return {"docs": [_doc_record(run, doc_id, r.final_url, t2 or title, md, r.body,
                                 f"{doc_id}.amp.{ext}", hidden)], "via": "amp"}


def _archive(run, crawler, idx, url):
    """The newest Wayback Machine snapshot, fetched through the same safe crawler."""
    if crawler.profile_for(url).get("no_archive"):
        return None
    try:
        api = crawler.fetch(ARCHIVE_API + quote(url, safe=""), types=("application/json",))
        snap = json.loads(api.body.decode("utf-8")).get("archived_snapshots", {}).get("closest")
        if not snap or not snap.get("available") or str(snap.get("status", "200")) != "200":
            return None
        ts = re.sub(r"\D", "", str(snap["timestamp"]))[:14]
        r = crawler.fetch(f"https://web.archive.org/web/{ts}id_/{url}")
    except (FetchError, ValueError, KeyError, AttributeError):
        return None
    md, hidden, title, ext = _convert(r)
    if not md.strip():
        return None
    doc_id = f"D{idx}"
    human = f"https://web.archive.org/web/{ts}/{url}"
    return {"docs": [_doc_record(run, doc_id, human, title or url, md, r.body,
                                 f"{doc_id}.archive.{ext}", hidden)],
            "via": "archive", "archived_at": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}",
            "archive_url": human}


def _fetch_item(run: Run, crawler: Crawler, idx: int, url: str, renderer=None) -> dict:
    """D-PR-15 order: crawler (with bounded retries) -> browser for thin or needs_js pages
    -> AMP -> archive. The paste step is offered by the sources phase."""
    profile = crawler.profile_for(url)
    try:
        res = crawler.fetch(url)
    except FetchError as e:
        if e.reason in NO_FALLBACK:
            raise
        alt = _archive(run, crawler, idx, url)
        if alt:
            return dict(alt, fell_back_from=e.reason)
        raise
    if res.content_type in FEED_TYPES:
        raise FetchError("is_feed", "start a new run with this URL to pick its articles")
    md, hidden, title, ext = _convert(res)
    doc_id = f"D{idx}"
    rec = _doc_record(run, doc_id, res.final_url, title or url, md, res.body,
                      f"{doc_id}.{ext}", hidden)
    item = {"docs": [rec], "final_url": res.final_url, "hops": res.hops, "via": "direct"}
    thin = ext == "html" and len(md) < THIN_PAGE_CHARS
    if ext == "html" and (thin or profile.get("needs_js")):
        steps = []
        if renderer is not None:
            steps.append(lambda: _rendered(run, crawler, renderer, idx, res.final_url, title))
        if thin:
            steps += [lambda: _amp(run, crawler, idx, res, title),
                      lambda: _archive(run, crawler, idx, url)]
        for step in steps:
            alt = step()
            if alt and alt["docs"][0]["chars"] >= THIN_PAGE_CHARS:
                return dict(item, **alt, fell_back_from="thin_page" if thin else "needs_js")
        if thin:
            item["warning"] = "thin_page_maybe_js_rendered" + ("" if renderer else
                                                                "; no_browser_installed")
    return item


def _path_item(run: Run, idx: int, value: str) -> dict:
    p = Path(value).expanduser()
    if p.is_symlink():
        raise ConvertError("symlink", value)
    if p.is_dir():
        docs, skipped = convert_folder(p)
        recs = []
        for k, d in enumerate(docs, 1):
            doc_id = f"D{idx}-{k}"
            ext = Path(d.origin).suffix.lstrip(".") or "txt"
            recs.append(_doc_record(run, doc_id, d.origin, d.title, d.markdown, d.raw,
                                    f"{doc_id}.{ext}", d.hidden))
        if not recs:
            raise ConvertError("no_supported_files", value)
        return {"docs": recs, "skipped": [{"origin": s.origin, "reason": s.reason}
                                          for s in skipped]}
    if not p.exists():
        raise ConvertError("not_found", value)
    d = convert_file(p)
    doc_id = f"D{idx}"
    ext = p.suffix.lstrip(".") or "txt"
    return {"docs": [_doc_record(run, doc_id, p.name, d.title, d.markdown, d.raw,
                                 f"{doc_id}.{ext}", d.hidden)]}


def _feed_item(run: Run, crawler: Crawler, idx: int, target: dict, renderer=None) -> dict:
    """An article listed by a feed. Its page is the source of truth (feeds can be
    lossy: iThome's strips punctuation); the feed's HTML is only the fallback."""
    try:
        item = _fetch_item(run, crawler, idx, target["value"], renderer)
        if item["docs"][0]["chars"]:
            item["docs"][0]["title"] = target.get("title") or item["docs"][0]["title"]
            return item
    except FetchError:
        pass
    conv = html_to_markdown(target.get("html", ""))
    doc_id = f"D{idx}"
    raw_name = f"{doc_id}.feed.html"
    return {"docs": [_doc_record(run, doc_id, target["value"], target.get("title") or conv.title,
                                 conv.markdown, target.get("html", "").encode("utf-8"),
                                 raw_name, conv.hidden)],
            "warning": "feed_content_maybe_lossy"}


def _text_item(run: Run, idx: int, value: str, pasted_for: str = "") -> dict:
    """Free text; pasted_for is the URL the user pasted it from (D-PR-15, step 4)."""
    doc_id = f"D{idx}"
    first = value.strip().splitlines()[0].lstrip("#").strip()[:60] if value.strip() else "text"
    item = {"docs": [_doc_record(run, doc_id, pasted_for, first, value.strip(),
                                 value.encode("utf-8"), f"{doc_id}.txt", [])]}
    if pasted_for:
        item["via"] = "paste"
    return item


def run_sources(run: Run, crawler: Crawler, *, on_progress=None, renderer=None) -> dict:
    intake = read_json(run.path("00-intake.json"))
    manifest_path = run.path("01-sources/manifest.json")
    manifest = read_json(manifest_path, default={"items": []})
    prior = {it["item"]: it for it in manifest.get("items", [])}
    items = []
    for idx, target in enumerate(intake["targets"], 1):
        old = prior.get(idx)
        if old and old.get("status") == "ok" and old.get("value") == target["value"]:
            items.append(old)
            continue
        entry = {"item": idx, "kind": target["kind"], "value": target["value"],
                 "attempted_at": datetime.now().isoformat(timespec="seconds")}
        try:
            if target["kind"] == "url":
                entry.update(_fetch_item(run, crawler, idx, target["value"], renderer))
            elif target["kind"] == "feed_item":
                entry.update(_feed_item(run, crawler, idx, target, renderer))
            elif target["kind"] == "path":
                entry.update(_path_item(run, idx, target["value"]))
            else:
                entry.update(_text_item(run, idx, target["value"], target.get("pasted_for", "")))
            entry["status"] = "ok"
        except (FetchError, ConvertError) as e:
            entry.update(status="failed", reason=e.reason, detail=str(e)[:300])
        items.append(entry)
        if on_progress:
            on_progress(entry)
    manifest = {"items": items}
    write_json(manifest_path, manifest)

    segs: dict[str, list[dict]] = {}
    hidden_all: list[dict] = []
    for it in items:
        for d in it.get("docs", []) if it.get("status") == "ok" else []:
            md = run.path(d["normalized"]).read_text(encoding="utf-8")
            md = re.sub(r"^<!-- source:.*?-->\s*", "", md, flags=re.S)
            doc_num = d["doc"][1:]
            segs[d["doc"]] = segment(md, doc_num)
            hidden_all += [dict(h, doc=d["doc"]) for h in d.get("hidden", [])]
    write_json(run.path("01-sources/segments.json"), segs)
    flat = [s for doc in segs.values() for s in doc]
    write_json(run.path("01-sources/injection-scan.json"), scan(flat, hidden_all))
    return manifest


def failed_items(manifest: dict) -> list[dict]:
    return [it for it in manifest.get("items", []) if it.get("status") != "ok"]
