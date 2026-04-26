"""Handle Shadow DOM traversal for Web Components, Lit, Stencil, etc."""
from playwright.sync_api import Page, Locator


class ShadowDomHandler:
    """
    Handles Shadow DOM traversal:
    - Web Components with attachShadow
    - Lit elements
    - Stencil components
    - Any Custom Element using shadow DOM
    """

    def locate_in_shadow_dom(
        self,
        page: Page,
        selectors: list[str],
        host_selector: str = "body",
    ) -> Locator | None:
        """
        Drill through a chain of shadow roots.

        selectors example: ["my-app", "#toolbar", "paper-button.primary"]
        Returns innermost Locator, or None if path not found.

        This works by executing JS to traverse shadow roots, then
        reconstructing a Playwright locator for the final element.
        """
        current_sel = host_selector

        for i, sel in enumerate(selectors):
            # Use JS to check if current host has shadow root
            has_shadow = page.evaluate(
                f"""(s) => {{
                    const el = document.querySelector(s);
                    if (!el) return false;
                    return el.shadowRoot !== null;
                }}""",
                current_sel,
            )

            if has_shadow:
                # Query inside shadow root via JS
                result = page.evaluate(
                    f"""(host, target) => {{
                        const el = document.querySelector(host);
                        if (!el || !el.shadowRoot) return null;
                        const found = el.shadowRoot.querySelector(target);
                        return found ? found.outerHTML.substring(0, 100) : null;
                    }}""",
                    current_sel,
                    sel,
                )
                if result is None:
                    return None
                # Shadow found; move to this element for next iteration
                current_sel = sel
            else:
                # No shadow DOM at this level, use normal query
                count = page.locator(current_sel).count()
                if count == 0:
                    return None
                # Use nested locator for the next selector
                current_sel = f"{current_sel} >> {sel}"

        return page.locator(current_sel) if current_sel != host_selector else None

    def get_shadow_dom_html(self, page: Page, host_selector: str) -> str:
        """Get the rendered HTML content inside a shadow root."""
        return page.evaluate(
            """(selector) => {
                const host = document.querySelector(selector);
                if (!host) return '';
                const sr = host.shadowRoot;
                return sr ? sr.innerHTML : '';
            }""",
            host_selector,
        )

    def click_in_shadow_dom(
        self,
        page: Page,
        host_selector: str,
        target_selector: str,
    ) -> bool:
        """Click an element inside a shadow DOM host."""
        found = page.evaluate(
            """(host, target) => {
                const el = document.querySelector(host);
                if (!el || !el.shadowRoot) return false;
                const targetEl = el.shadowRoot.querySelector(target);
                if (targetEl) { targetEl.click(); return true; }
                return false;
            }""",
            host_selector,
            target_selector,
        )
        return bool(found)

    def fill_in_shadow_dom(
        self,
        page: Page,
        host_selector: str,
        target_selector: str,
        value: str,
    ) -> bool:
        """Fill an input inside a shadow DOM host."""
        found = page.evaluate(
            """(host, target, value) => {
                const el = document.querySelector(host);
                if (!el || !el.shadowRoot) return false;
                const targetEl = el.shadowRoot.querySelector(target);
                if (targetEl && (targetEl.tagName === 'INPUT' || targetEl.tagName === 'TEXTAREA')) {
                    targetEl.value = value;
                    targetEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    targetEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }
                return false;
            }""",
            host_selector,
            target_selector,
            value,
        )
        return bool(found)
