"""Handle iframes, frames, and nested iframe chains."""
from playwright.sync_api import Page, FrameLocator
from typing import Callable


class IframeHandler:
    """
    Handles:
    - <iframe>, <frame>, and nested iframe chains
    - srcdoc iframes
    - sandboxed iframes
    - Cross-origin iframes (detect and skip or report)
    """

    def get_all_iframes(self, page: Page) -> list[dict]:
        """Find all iframes on the page with their metadata."""
        return page.evaluate(
            """() => {
                return Array.from(document.querySelectorAll('iframe, frame')).map(el => ({
                    src: el.src || (el.srcdoc ? '(srcdoc)' : ''),
                    id: el.id || '',
                    name: el.name || '',
                    width: el.width || el.offsetWidth,
                    height: el.height || el.offsetHeight,
                    sandbox: el.sandbox?.value || '',
                    visible: el.offsetParent !== null,
                }));
            }"""
        )

    def get_frame_locator(self, page: Page, selector: str) -> FrameLocator:
        """Get a FrameLocator for the given iframe selector."""
        return page.frame_locator(selector)

    def switch_to_frame(self, page: Page, selector: str) -> FrameLocator:
        """Switch context to an iframe, returning a FrameLocator for chaining."""
        return page.frame_locator(selector)

    def interact_in_iframe(
        self,
        page: Page,
        iframe_selector: str,
        action_fn: Callable[[Page], None],
        timeout_ms: int = 10000,
    ):
        """
        Execute an action inside a specific iframe, then return to main context.

        action_fn receives a Page-like proxy object (IframePage) that supports
        locator(), click(), fill(), wait_for_timeout().
        """
        fl = page.frame_locator(iframe_selector)

        class IframePage:
            def locator(self, sel: str):
                return fl.locator(sel)

            def click(self, sel: str, **kwargs):
                return fl.locator(sel).click(**kwargs)

            def fill(self, sel: str, val: str, **kwargs):
                return fl.locator(sel).fill(val, **kwargs)

            def select_option(self, sel: str, val: str | list[str], **kwargs):
                return fl.locator(sel).select_option(val, **kwargs)

            def wait_for_selector(self, sel: str, **kwargs):
                return fl.locator(sel).wait_for(**kwargs)

            def wait_for_timeout(self, ms: int):
                import time
                time.sleep(ms / 1000)

            def inner_text(self, sel: str) -> str:
                return fl.locator(sel).inner_text()

            def is_visible(self, sel: str) -> bool:
                return fl.locator(sel).is_visible()

        frame_page = IframePage()
        action_fn(frame_page)

    def try_click_in_iframe(
        self,
        page: Page,
        iframe_selector: str,
        element_selector: str,
    ) -> bool:
        """
        Try to click an element inside an iframe.
        Returns True if successful, False otherwise.
        """
        try:
            fl = page.frame_locator(iframe_selector)
            loc = fl.locator(element_selector)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=5000)
                return True
        except Exception:
            pass
        return False

    def detect_cross_origin_iframes(self, page: Page) -> list[dict]:
        """Detect iframes that cross origin boundaries (cannot be accessed)."""
        return page.evaluate(
            """() => {
                const results = [];
                const mainOrigin = window.location.origin;
                document.querySelectorAll('iframe').forEach(iframe => {
                    try {
                        const src = iframe.src || '';
                        const iframeWin = iframe.contentWindow;
                        if (!iframeWin) {
                            results.push({ selector: '', src, cross_origin: true, reason: 'no_content_window' });
                            return;
                        }
                        const iframeDoc = iframeWin.document;
                        results.push({ selector: '', src, cross_origin: src && !src.startsWith(mainOrigin) && src.startsWith('http'), reason: '' });
                    } catch (e) {
                        results.push({ selector: '', src: iframe.src || '', cross_origin: true, reason: String(e) });
                    }
                });
                return results;
            }"""
        )
