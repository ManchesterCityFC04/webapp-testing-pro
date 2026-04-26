"""
Full 3-phase example: discover → plan → execute → report.
Run with: python examples/full_3phase_example.py
"""
import asyncio
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.discover import crawl_site, SiteMap
from src.checklist import ChecklistGenerator
from src.report import CoverageReporter
from src.interact import ModalHandler, ScrollHelper, MultiStepFormHandler, FormStep

ARTIFACTS = Path(__file__).parent.parent / "test-artifacts" / "webapp-autotest"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
SCREENSHOTS = ARTIFACTS / "screenshots"
SCREENSHOTS.mkdir(exist_ok=True)


def safe_screenshot(page, name: str) -> Path:
    path = SCREENSHOTS / f"{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass
    return path


def collect_console_errors(page) -> list[str]:
    errors = []
    def on_console(msg):
        if msg.type == "error":
            errors.append(f"[{msg.type}] {msg.text}")
    page.on("console", on_console)
    return errors


def test_url(page, url: str, name: str, results: list[dict]):
    """Test a single URL: navigate, screenshot, collect errors."""
    print(f"  Testing: {url}")
    errors = collect_console_errors(page)
    screenshot = safe_screenshot(page, name)

    # Try to interact with visible buttons
    try:
        page.goto(url, wait_until="networkidle", timeout=20000)
        buttons = page.locator("button").all()
        if buttons:
            # Click the first visible button
            for btn in buttons:
                if btn.is_visible() and not btn.is_disabled():
                    btn.click()
                    page.wait_for_timeout(500)
                    break
    except Exception as e:
        errors.append(f"Navigation error: {e}")

    results.append({
        "url": url,
        "status": "PASS" if not errors else "FAIL",
        "screenshot": str(screenshot),
        "console_errors": errors,
        "notes": f"Page loaded, {len(errors)} console errors",
    })


def main():
    base_url = "http://localhost:3000"

    # ── Phase 1: Discover ──────────────────────────────────────────────
    print("\n[Phase 1] Discovering routes...")
    sitemap = crawl_site(base_url, max_depth=3, max_pages=100)

    # Save sitemap
    sitemap_path = ARTIFACTS / "sitemap.json"
    json.dump(sitemap.to_dict(), open(sitemap_path, "w"), indent=2, ensure_ascii=False)
    print(f"  Discovered {len(sitemap.routes)} routes -> {sitemap_path}")

    # ── Phase 2: Plan ─────────────────────────────────────────────────
    print("\n[Phase 2] Generating checklist...")
    checklist = ChecklistGenerator(sitemap).generate()
    checklist_path = ARTIFACTS / "checklist.md"
    checklist_path.write_text(checklist, encoding="utf-8")
    print(f"  Checklist -> {checklist_path}")
    print(checklist[:500] + "...")

    # ── Phase 3: Execute ──────────────────────────────────────────────
    print("\n[Phase 3] Executing tests...")
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        mh = ModalHandler()
        sh = ScrollHelper()

        # Test critical pages (up to 10)
        for r in sitemap.routes[:10]:
            if r.route_type.value != "page":
                continue
            name = r.url.replace(base_url, "").replace("/", "_").strip("_") or "root"
            test_url(page, r.url, name, results)

        # Example: test a multi-step form if found
        forms_with_steps = [r for r in sitemap.routes if len(r.forms) > 0]
        if forms_with_steps:
            route = forms_with_steps[0]
            print(f"  Testing multi-step form: {route.url}")
            try:
                page.goto(route.url, wait_until="networkidle", timeout=20000)
                msf = MultiStepFormHandler(page, artifacts_dir=str(SCREENSHOTS))

                # Try to click first form submit button found
                submit_btn = page.locator("button[type='submit']").first
                if submit_btn.count() > 0 and submit_btn.is_visible():
                    safe_screenshot(page, "form_step_attempt")
                    results.append({
                        "url": route.url,
                        "status": "PASS",
                        "screenshot": str(SCREENSHOTS / "form_step_attempt.png"),
                        "notes": msf.get_summary(),
                    })
            except Exception as e:
                results.append({
                    "url": route.url,
                    "status": "FAIL",
                    "console_errors": [str(e)],
                    "notes": "Form test failed",
                })

        browser.close()

    # ── Report ────────────────────────────────────────────────────────
    print("\n[Report] Generating coverage report...")
    report = CoverageReporter(sitemap, results, artifacts_dir=str(ARTIFACTS)).generate()
    report_path = ARTIFACTS / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  Report -> {report_path}")
    print("\n" + report[:800] + "\n...")

    print("\n✅ All 3 phases complete!")
    print(f"   Sitemap: {sitemap_path}")
    print(f"   Checklist: {checklist_path}")
    print(f"   Report: {report_path}")


if __name__ == "__main__":
    main()
