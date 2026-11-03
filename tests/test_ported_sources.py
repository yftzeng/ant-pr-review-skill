"""Source fixes ported from ant-peer-review (fetch limits, agent-ready forms, the main
region, titles, long pasted lines)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ant_pr_review.i18n import T
from ant_pr_review.jsonio import read_json
from ant_pr_review.sources.crawler import Crawler
from test_fallback import FULL, THIN, URL, FakeCrawler, FakeRenderer, archived, run_for, text_of

REPO = "https://github.com/acme/widget"
RAW = "https://raw.githubusercontent.com/acme/widget/HEAD/README.md"
README = '<p align="center"><img src="a.png"></p>\n\n<h1>Widget</h1>\n\n' + \
    "A README paragraph that explains the project in words. " * 8


# @S-source-acquisition-045
def test_fetch_limits_defaults_and_config(tmp_path):
    from ant_pr_review.pipeline import make_crawler
    from ant_pr_review.store import Store
    store = Store(tmp_path / "home")
    c = make_crawler(store)
    assert (c.connect_timeout, c.timeout, c.deadline, c.url_budget) == (5.0, 10.0, 30.0, 90.0)
    store.home.mkdir(parents=True, exist_ok=True)
    store.config_path.write_text('lang = "en"\n\n[fetch]\nconnect = 2\nread = 4\npage = 8\n'
                                 'url_budget = 20\n')
    c = make_crawler(store)
    assert (c.connect_timeout, c.timeout, c.deadline, c.url_budget) == (2.0, 4.0, 8.0, 20.0)
    store.save_config(store.load_config())
    assert "[fetch]" in store.config_path.read_text() and make_crawler(store).url_budget == 20.0


# @S-source-acquisition-045
def test_url_budget_stops_the_fallbacks(tmp_path):
    c = FakeCrawler(pages={URL: ("text/html", THIN), **archived()})
    c.url_budget = 0
    r = FakeRenderer()
    run, item = run_for(tmp_path, c, r)
    assert r.calls == [] and c.calls == [URL] and "url_budget_exceeded" in item["warning"]
    c = FakeCrawler(pages=archived(), fail={URL: "timeout"})
    c.url_budget = 0
    run, item = run_for(tmp_path / "b", c)
    assert item["status"] == "failed" and c.calls == [URL]


# @S-source-acquisition-046
def test_github_repo_read_from_raw_readme(tmp_path):
    c = FakeCrawler(pages={RAW: ("text/plain", README)})
    run, item = run_for(tmp_path, c, url=REPO)
    assert c.calls == [RAW] and item["status"] == "ok" and item["via"] == "github_readme"
    assert item["docs"][0]["title"] == "Widget" and "A README paragraph" in text_of(run)
    assert "<p" not in text_of(run) and T("en")("via.github_readme") == "GitHub README (raw)"
    page = "<html><body><article class='markdown-body'>" + \
        "".join(f"<p>Rendered README paragraph {i} with enough words in it.</p>" for i in range(8)) + \
        "</article></body></html>"
    c = FakeCrawler(pages={REPO: ("text/html", page)})          # raw missing: the page as before
    run, item = run_for(tmp_path / "c", c, url=REPO)
    assert c.calls == [RAW, REPO] and item["via"] == "direct"


class Echo(BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):
        if self.path == "/robots.txt":
            self.send_response(404)
            self.end_headers()
            return
        Echo.seen.append(self.headers.get("Accept"))
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown")
        self.end_headers()
        self.wfile.write(b"# Title\n\nPlain markdown body.")

    def log_message(self, *a):
        pass


# @S-source-acquisition-046
def test_markdown_asked_first():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Echo)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = Crawler(resolver=lambda h, p: ["127.0.0.1"], min_interval=0,
                    _allow_hosts_for_tests=frozenset({"pub.example"}))
        res = c.fetch(f"http://pub.example:{srv.server_address[1]}/a")
        assert Echo.seen[-1].startswith("text/markdown, text/html;q=0.9, ")
        assert res.content_type == "text/markdown" and res.body.startswith(b"# Title")
    finally:
        srv.shutdown()


LD = {"@context": "https://schema.org", "@graph": [
    {"@type": "WebSite", "name": "Site"},
    {"@type": "NewsArticle", "headline": "LD title",
     "articleBody": " ".join(["The full article body sentence from structured data."] * 10)}]}


# @S-source-acquisition-046
def test_jsonld_body_only_for_thin_pages(tmp_path):
    body = THIN.decode().split("<body>")[1].split("</body>")[0]
    thin = (f"<html><head><title>T</title><script type='application/ld+json'>{json.dumps(LD)}"
            f"</script></head><body>{body}</body></html>")
    r = FakeRenderer()
    run, item = run_for(tmp_path, FakeCrawler(pages={URL: ("text/html", thin)}), r)
    assert r.calls == [] and item["via"] == "jsonld" and item["fell_back_from"] == "thin_page"
    assert "full article body sentence from structured data" in text_of(run)
    full = FULL.replace("</head>", f"<script type='application/ld+json'>{json.dumps(LD)}</script></head>")
    run, item = run_for(tmp_path / "b", FakeCrawler(pages={URL: ("text/html", full)}), FakeRenderer())
    assert item["via"] == "direct" and "structured data" not in text_of(run)
    assert read_json(run.path("01-sources/manifest.json"))["items"][0]["via"] == "direct"
    assert T("zh-TW")("via.jsonld").startswith("JSON-LD")


# @S-source-acquisition-047
def test_main_region_is_the_article_with_most_text():
    from ant_pr_review.sources.htmlmd import html_to_markdown
    story = "".join(f"<p>Story paragraph {i} with enough words to count as body.</p>" for i in range(8))
    md = html_to_markdown(f"<html><body><article><p>Teaser card: read this other piece</p></article>"
                          f"<article>{story}</article></body></html>").markdown
    assert "Story paragraph 7" in md and "Teaser card" not in md
    md = html_to_markdown(f"<html><body><article><p>Nice post, thanks!</p></article>"
                          f"<div class='post-content'>{story}</div></body></html>").markdown
    assert "Story paragraph 0" in md and "Nice post" not in md
    bib = "@misc{x2026, title = {Sparks}, author = {A and B and C}, year = {2026}, note = {Blog post} } " * 3
    long_story = "".join(f"<p>Story paragraph {i}: a long body with many more words in it.</p>"
                         for i in range(40))
    md = html_to_markdown(f"<html><body><d-article>{long_story}</d-article><div class='citation-article'>"
                          f"<article><pre>{bib}</pre></article></div></body></html>").markdown
    assert "Story paragraph 39" in md and "Story paragraph 0" in md       # a sliver does not count
    import time
    t0 = time.monotonic()
    html_to_markdown("<article><p>x</p></article>" * 5000 + f"<article>{story}</article>")
    assert time.monotonic() - t0 < 3                                    # at most 50 compared


# @S-source-acquisition-048
def test_titles_read_as_text():
    from ant_pr_review.sources.htmlmd import html_to_markdown
    from ant_pr_review.sources.agentready import jsonld
    raw = "Read &amp; write &#8212; a &quot;test&quot;"
    html = (f"<html><head><title>{raw}</title><script type='application/ld+json'>"
            f"{json.dumps({'@type': 'Article', 'headline': raw})}</script></head><body></body></html>")
    assert html_to_markdown(html).title == 'Read & write — a "test"'
    assert jsonld(html)["title"] == 'Read & write — a "test"'


# @S-cli-015
def test_long_pasted_line_is_text_and_names_the_run():
    import re
    from pathlib import Path
    from ant_pr_review.cli import slug_for
    from ant_pr_review.intake import classify_target
    line = "公司昨晚發生資料外洩，客戶個資可能流出，媒體已經在問，我們還不清楚範圍。" * 6 + " https://news.example/a/"
    assert len(line.encode()) > 255
    assert classify_target(line) == {"kind": "text", "value": line}
    assert slug_for(line) == line[:40]
    src = Path(__file__).parents[1] / "src" / "ant_pr_review"
    direct = re.compile(r"Path\([^()]*\)(?:\.expanduser\(\))?\.exists\(")
    hits = [f"{f.relative_to(src)}:{i}" for f in src.rglob("*.py")
            for i, l in enumerate(f.read_text().splitlines(), 1) if direct.search(l)]
    assert hits == [], f"check typed paths with intake.existing_path: {hits}"
