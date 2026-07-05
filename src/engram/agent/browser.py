"""Playwright wrapper: actions + the two observations the vision model needs.

Screenshot (downscaled JPEG) for layout, DOM snapshot (compact interactive
tree with real selectors) for grounding — selectors beat pixel guessing.
"""
from __future__ import annotations

import base64
from types import TracebackType
from typing import Any

from playwright.sync_api import Browser as PWBrowser
from playwright.sync_api import Page, Playwright, sync_playwright

VIEWPORT = {"width": 1280, "height": 900}
STEP_TIMEOUT_MS = 15_000

_DOM_SNAPSHOT_JS = """
() => {
  const sel = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 4) {
      let p = el.tagName.toLowerCase();
      if (el.name) { p += `[name="${el.name}"]`; parts.unshift(p); break; }
      const sibs = el.parentNode ? [...el.parentNode.children].filter(c => c.tagName === el.tagName) : [];
      if (sibs.length > 1) p += `:nth-of-type(${sibs.indexOf(el) + 1})`;
      parts.unshift(p);
      el = el.parentNode;
    }
    return parts.join(' > ');
  };
  const interactive = [...document.querySelectorAll(
    'a[href], button, input, select, textarea, [role=button], [onclick]')];
  const lines = interactive.slice(0, 60).map(el => {
    const label = (el.labels && el.labels[0]?.innerText) || el.getAttribute('aria-label')
      || el.innerText || '';
    let line = `${el.tagName.toLowerCase()} sel=${sel(el)} text="${label.trim().slice(0, 60)}"`;
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      line += ` value="${(el.value || '').slice(0, 40)}"`;      // EMPTY means not filled
      line += ` placeholder="${(el.placeholder || '').slice(0, 40)}"`;
    }
    return line;
  });
  const headings = [...document.querySelectorAll('h1,h2,h3')].slice(0, 10)
    .map(h => `${h.tagName.toLowerCase()}: ${h.innerText.trim().slice(0, 80)}`);
  return ['# headings', ...headings, '# interactive', ...lines].join('\\n');
}
"""


class BrowserSession:
    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._pw: Playwright | None = None
        self._browser: PWBrowser | None = None
        self.page: Page | None = None

    def __enter__(self) -> "BrowserSession":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self.page = self._browser.new_page(viewport=VIEWPORT)
        self.page.set_default_timeout(STEP_TIMEOUT_MS)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    # -- observations --------------------------------------------------------

    def screenshot_b64(self) -> str:
        assert self.page is not None
        raw = self.page.screenshot(type="jpeg", quality=60)
        return base64.b64encode(raw).decode()

    def screenshot_save(self, path: str) -> None:
        assert self.page is not None
        self.page.screenshot(type="jpeg", quality=60, path=path)

    def dom_snapshot(self) -> str:
        assert self.page is not None
        return str(self.page.evaluate(_DOM_SNAPSHOT_JS))

    @property
    def url(self) -> str:
        assert self.page is not None
        return self.page.url

    # -- actions -------------------------------------------------------------

    def act(self, action: str, target: str, value: str | None = None) -> str:
        """Execute one Step-shaped action; returns extracted text for 'extract'."""
        assert self.page is not None
        page = self.page
        if action == "goto":
            page.goto(target)
        elif action == "click":
            page.click(target)
        elif action == "fill":
            page.fill(target, value or "")
        elif action == "press":
            page.keyboard.press(target)
        elif action == "wait_for":
            page.wait_for_selector(target)
        elif action == "extract":
            return page.inner_text(target).strip()
        else:
            raise ValueError(f"unknown action: {action}")
        return ""


def act_with_fallback(
    session: BrowserSession,
    action: str,
    target: str,
    value: str | None = None,
    fallback_selector: str | None = None,
) -> tuple[str, bool]:
    """Try target, then fallback. Returns (extracted_text, used_fallback)."""
    try:
        return session.act(action, target, value), False
    except Exception:
        if not fallback_selector:
            raise
        return session.act(action, fallback_selector, value), True
