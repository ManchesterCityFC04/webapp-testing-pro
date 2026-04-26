"""Handle infinite scroll, lazy-loaded tables, and virtualized lists."""
from playwright.sync_api import Page


class ScrollHelper:
    """
    Handles:
    - Infinite scroll (social media style: new content loads on scroll)
    - Lazy-loaded tables (Ant Design Table, Material Table, etc.)
    - 'Load More' buttons
    - Virtualized/scrollable containers
    """

    def scroll_until_stable(
        self,
        page: Page,
        item_selector: str,
        max_scrolls: int = 20,
        stable_threshold: int = 3,
        scroll_delay_ms: int = 1500,
    ) -> int:
        """
        Scroll to bottom repeatedly until the number of items stops increasing
        for `stable_threshold` consecutive scrolls.
        Returns total number of items found.
        """
        prev_count = 0
        stable_count = 0

        for _ in range(max_scrolls):
            current = page.locator(item_selector).count()

            if current == prev_count:
                stable_count += 1
                if stable_count >= stable_threshold:
                    return current
            else:
                stable_count = 0

            prev_count = current
            self._scroll_to_bottom(page, item_selector)
            page.wait_for_timeout(scroll_delay_ms)

        return page.locator(item_selector).count()

    def _scroll_to_bottom(self, page: Page, item_selector: str):
        """Scroll the nearest scrollable ancestor of item_selector to its bottom."""
        page.evaluate(
            f"""(sel) => {{
                const el = document.querySelector(sel)?.closest('[style*="overflow"], .ant-table-body, .ant-list, .virtual-list, main, section, div');
                if (el && el.scrollHeight > el.clientHeight) {{
                    el.scrollTop = el.scrollHeight;
                }} else {{
                    window.scrollTo(0, document.body.scrollHeight);
                }}
            }}""",
            item_selector,
        )

    def scroll_to_element(self, page: Page, selector: str, smooth: bool = True):
        """Smooth-scroll to a specific element."""
        page.evaluate(
            f"""(sel) => {{
                const el = document.querySelector(sel);
                if (el) {{ el.scrollIntoView({{ behavior: '{'smooth' if smooth else 'instant'}' }}); }}
            }}""",
            selector,
        )
        page.wait_for_timeout(300)

    def click_load_more(self, page: Page, button_selector: str = "button:has-text('Load More'), button:has-text('加载更多'), [class*='load-more']") -> int:
        """
        Repeatedly click 'Load More' button until it disappears or times out.
        Returns number of times clicked.
        """
        clicks = 0
        while page.locator(button_selector).count() > 0:
            btn = page.locator(button_selector).first
            if not btn.is_visible():
                break
            try:
                btn.click()
                page.wait_for_timeout(1500)
                clicks += 1
            except Exception:
                break
        return clicks

    def wait_for_lazy_content(self, page: Page, content_selector: str, timeout_ms: int = 10000) -> bool:
        """Wait for lazy-loaded content to appear within a container."""
        import time
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            count = page.locator(content_selector).count()
            if count > 0:
                return True
            page.wait_for_timeout(500)
        return False
