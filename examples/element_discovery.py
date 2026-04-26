"""Comprehensive element discovery for webapp-autotest.

Discovers all buttons, links, forms, inputs, iframes, and interactive elements
on a page. This is the Phase 1 building block used by the crawler.
"""
import os
from playwright.sync_api import sync_playwright

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "test-artifacts", "screenshots")


def discover_page(url: str, screenshot_path: str | None = None) -> dict:
    """
    Discover all interactive elements on a page.
    Returns a dict with buttons, links, forms, inputs, iframes.
    """
    results = {
        "url": url,
        "buttons": [],
        "links": [],
        "forms": [],
        "inputs": [],
        "iframes": [],
        "selectors": {
            "buttons": "button, [role='button'], input[type='button'], input[type='submit'], a.btn, .btn",
            "links": "a[href]",
            "forms": "form",
            "inputs": "input, textarea, select",
            "iframes": "iframe, frame",
        },
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        page.goto(url)
        page.wait_for_load_state("networkidle")

        if screenshot_path:
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            page.screenshot(path=screenshot_path, full_page=True)

        # Buttons
        for btn in page.locator(results["selectors"]["buttons"]).all():
            try:
                results["buttons"].append({
                    "text": btn.inner_text().strip(),
                    "visible": btn.is_visible(),
                    "disabled": btn.is_disabled(),
                    "role": btn.get_attribute("role") or "button",
                    "classes": btn.get_attribute("class") or "",
                })
            except Exception:
                pass

        # Links
        for link in page.locator(results["selectors"]["links"]).all():
            try:
                href = link.get_attribute("href") or ""
                if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    results["links"].append({
                        "text": link.inner_text().strip(),
                        "href": href,
                        "visible": link.is_visible(),
                    })
            except Exception:
                pass

        # Forms
        for form in page.locator("form").all():
            try:
                fields = []
                for inp in form.locator("input, select, textarea").all():
                    fields.append({
                        "name": inp.get_attribute("name") or "",
                        "id": inp.get_attribute("id") or "",
                        "type": inp.get_attribute("type") or "text",
                        "tag": inp.evaluate("el => el.tagName"),
                        "required": inp.get_attribute("required") is not None,
                    })
                results["forms"].append({
                    "action": form.get_attribute("action") or "",
                    "method": form.get_attribute("method") or "get",
                    "fields": fields,
                })
            except Exception:
                pass

        # Inputs (outside forms)
        for inp in page.locator("input:not(form input), select:not(form select), textarea:not(form textarea)").all():
            try:
                results["inputs"].append({
                    "name": inp.get_attribute("name") or "",
                    "id": inp.get_attribute("id") or "",
                    "type": inp.get_attribute("type") or "text",
                    "tag": inp.evaluate("el => el.tagName"),
                    "placeholder": inp.get_attribute("placeholder") or "",
                    "required": inp.get_attribute("required") is not None,
                })
            except Exception:
                pass

        # Iframes
        for iframe in page.locator("iframe, frame").all():
            try:
                results["iframes"].append({
                    "src": iframe.get_attribute("src") or "(srcdoc)",
                    "id": iframe.get_attribute("id") or "",
                    "name": iframe.get_attribute("name") or "",
                    "visible": iframe.is_visible(),
                    "sandbox": iframe.get_attribute("sandbox") or "",
                })
            except Exception:
                pass

        browser.close()

    return results


def print_discovery(results: dict):
    """Pretty-print discovery results."""
    print(f"\n=== Element Discovery: {results['url']} ===\n")

    print(f"Buttons ({len(results['buttons'])}):")
    for b in results["buttons"]:
        marker = "🔘" if b["visible"] and not b["disabled"] else "⏸️"
        print(f"  {marker} [{b['role']}] {b['text'][:50]}")

    print(f"\nLinks ({len(results['links'])}):")
    for link in results["links"][:10]:
        print(f"  🔗 {link['text'][:40]} -> {link['href'][:60]}")
    if len(results["links"]) > 10:
        print(f"  ... and {len(results['links']) - 10} more")

    print(f"\nForms ({len(results['forms'])}):")
    for f in results["forms"]:
        field_names = [ff["name"] for ff in f["fields"] if ff["name"]]
        print(f"  📋 {f['method'].upper()} {f['action'][:50]} — fields: {field_names or 'auto-detect'}")

    print(f"\nInputs (outside forms, {len(results['inputs'])}):")
    for inp in results["inputs"][:8]:
        print(f"  ✏️  [{inp['type']}] {inp['name'] or inp['id'] or '(unnamed)'}")

    print(f"\nIframes ({len(results['iframes'])}):")
    for iframe in results["iframes"]:
        cross = "🌐" if iframe["sandbox"] else "📄"
        print(f"  {cross} {iframe['id'] or iframe['name'] or iframe['src'][:50]}")


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    screenshot = os.path.join(OUTPUT_DIR, "discovery.png")
    results = discover_page(url, screenshot)
    print_discovery(results)
    print(f"\nScreenshot: {screenshot}")
