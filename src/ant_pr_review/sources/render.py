"""Headless-browser rendering for JS-rendered pages (D-PR-15, step 2).

Optional: needs the `render` extra (`pip install 'ant-pr-review[render]'` then
`playwright install chromium`). Used only for thin pages or `needs_js` site
profiles, after robots and the site profile were checked. The browser keeps its
own (honest) User-Agent; every request it makes passes `allow`, the same
address check as the crawler's, and anything else is aborted.
"""
from __future__ import annotations

import importlib.util
from typing import Callable, Protocol


class RenderError(Exception):
    pass


class Renderer(Protocol):
    def render(self, url: str, *, allow: Callable[[str], bool], max_bytes: int,
               timeout: float) -> str:
        """Return the rendered HTML of url."""


class PlaywrightRenderer:
    name = "playwright"

    def __init__(self, launch_args: tuple[str, ...] = ()):
        self.launch_args = list(launch_args)

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("playwright") is not None

    def render(self, url, *, allow, max_bytes, timeout) -> str:  # pragma: no cover - needs a browser
        from playwright.sync_api import Error, sync_playwright

        def route(r):
            if allow(r.request.url):
                r.continue_()
            else:
                r.abort()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=self.launch_args)
                try:
                    page = browser.new_context(java_script_enabled=True,
                                               service_workers="block").new_page()
                    page.route("**/*", route)
                    page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                    html = page.content()
                finally:
                    browser.close()
        except Error as e:
            raise RenderError(str(e)[:300]) from e
        if len(html.encode("utf-8")) > max_bytes:
            raise RenderError(f"rendered page larger than {max_bytes} bytes")
        return html


def default_renderer() -> Renderer | None:
    return PlaywrightRenderer() if PlaywrightRenderer.available() else None
