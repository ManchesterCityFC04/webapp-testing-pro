# webapp-autotest

**AI Agent-native webapp testing skill.**  
Crawl any webapp → generate a test checklist → execute with evidence → report coverage.

Use when: the user asks to test a webapp, verify functionality, run E2E checks, or audit a web application's pages and interactions.

---

## Core Problem

LLMs test webapps randomly and declare "all tests pass" after touching a few pages. The real coverage is invisible. This skill solves it with a **three-phase protocol**:
1. **Discover** — crawl the full site structure before testing
2. **Plan** — generate a mandatory checklist organized by priority
3. **Execute** — test every item with evidence, handle complex UI patterns, report honestly

---

## Workflow

### Phase 1 · Discover

```
Goal: Build a complete inventory of all routes, forms, and links.
```

**Step 1: Detect tech stack**
```python
from src.discover import detect_tech_stack, get_route_source_dir

stack = detect_tech_stack(project_root)  # "nextjs" | "rails" | "django" | "laravel" | "plain"
```

**Step 2: Discover routes (5-strategy cascade — use all that apply)**

```python
import json
import asyncio
from src.discover import (
    SiteMap,
    analyze_nextjs_pages,
    analyze_nextjs_api,
    crawl_site,
    parse_sitemap,
)
from pathlib import Path

base_url = "http://localhost:3000"  # or from config
project_root = "."  # current project root
sitemap = SiteMap(base_url=base_url)

# Strategy 1: Static analysis (fastest, no browser needed)
if stack == "nextjs":
    src_dir = get_route_source_dir(project_root, stack)
    if src_dir:
        for r in analyze_nextjs_pages(src_dir, base_url):
            sitemap.routes.append(r)
        # Also discover API routes
        api_dir = Path(src_dir) / "api"
        for r in analyze_nextjs_api(str(api_dir), base_url):
            sitemap.routes.append(r)

# Strategy 2: sitemap.xml + robots.txt (for deployed sites)
sitemaps = await parse_sitemap(base_url)
for url in sitemaps:
    from src.discover.models import DiscoveredRoute, RouteType
    sitemap.routes.append(DiscoveredRoute(url=url, discovered_via="sitemap", route_type=RouteType.PAGE))

# Strategy 3: Playwright crawler (primary for running SPAs)
sitemap = crawl_site(base_url, max_depth=3, max_pages=200)

# Strategy 4: Auth-aware crawl (if login detected)
sitemap_auth = crawl_site(
    base_url,
    max_depth=3,
    auth_credentials={"username": "admin", "password": "Admin123"},
    login_url="/login",
)

# Strategy 5: Merge and deduplicate
sitemap.discovery_strategies_used = list(set([...]))  # merge from all strategies

# Save to disk
Path("test-artifacts/webapp-autotest/sitemap.json").parent.mkdir(parents=True, exist_ok=True)
json.dump(sitemap.to_dict(), open("test-artifacts/webapp-autotest/sitemap.json", "w"), indent=2)
```

**Output:** `test-artifacts/webapp-autotest/sitemap.json` — all discovered routes, forms, params, and links.

---

### Phase 2 · Plan

```
Goal: Generate a mandatory test checklist from the sitemap.
Every item must have a PASS/FAIL/SKIP outcome — no blank items allowed.
```

**Generate checklist:**
```python
from src.checklist.generator import ChecklistGenerator

gen = ChecklistGenerator(sitemap)
checklist_md = gen.generate()
Path("test-artifacts/webapp-autotest/checklist.md").write_text(checklist_md)
```

**Checklist structure:**
```markdown
# webapp-autotest Checklist

**Base URL**: http://localhost:3000
**Discovered**: 2026-04-26 10:00
**Total Routes**: 47 pages, 12 API routes

---

## Phase A: Critical (Priority 1)

### A1. Authentication
- [ ] `/login` — Login form renders, accepts credentials, redirects to dashboard
  - **Strategy**: ModalHandler.handle_modal + auto-login flow
  - **Skip reason**: ___________

- [ ] `/incidents` — Incident list loads, table renders, pagination works
  - **Strategy**: ScrollHelper.scroll_until_stable + pagination click
  - **Skip reason**: ___________

---

## Phase B: Standard (Priority 2)

- [ ] `/reports` — Report list renders
  - **Strategy**: navigate_and_wait; verify table or card list
  - **Skip reason**: ___________
```

**Critical rules enforced by this skill:**
- ❌ **Never start Phase 3 without a completed checklist**
- ❌ **Never skip Critical (Priority 1) items without an explicit skip reason**
- ❌ **Leave any checklist item blank — every item requires PASS/FAIL/SKIP**

---

### Phase 3 · Execute

```
Goal: Test every checklist item, collect evidence, produce a coverage report.
```

**Execution pattern per checklist item:**
```python
import os
from playwright.sync_api import sync_playwright
from src.interact import (
    ModalHandler,
    ScrollHelper,
    ShadowDomHandler,
    IframeHandler,
    MultiStepFormHandler,
    FormStep,
)

ARTIFACTS = "test-artifacts/webapp-autotest"
SCREENSHOTS = f"{ARTIFACTS}/screenshots"
os.makedirs(SCREENSHOTS, exist_ok=True)

results = []  # list of dicts: {url, status, screenshot, console_errors, notes}

def safe_screenshot(page, name: str, full_page: bool = False):
    path = f"{SCREENSHOTS}/{name}.png"
    try:
        page.screenshot(path=path, full_page=full_page)
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

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    modal_handler = ModalHandler()
    scroll_helper = ScrollHelper()
    iframe_handler = IframeHandler()
    shadow_handler = ShadowDomHandler()

    # --- Example: test a list page with pagination ---
    url = "http://localhost:3000/incidents"
    page.goto(url, wait_until="networkidle", timeout=30000)
    errors = collect_console_errors(page)
    safe_screenshot(page, "incidents_list")

    # Infinite scroll / lazy load
    row_count = scroll_helper.scroll_until_stable(
        page, ".ant-table-row, tr[data-row-key], .list-item", max_scrolls=10
    )

    # Pagination: try clicking next page
    next_btn = page.locator("button:has-text('下一页'), .ant-pagination-next:not(.ant-pagination-disabled)")
    if next_btn.count() > 0:
        next_btn.first.click()
        page.wait_for_timeout(1000)
        safe_screenshot(page, "incidents_page2")

    results.append({
        "url": url,
        "status": "PASS",
        "screenshot": f"{SCREENSHOTS}/incidents_list.png",
        "console_errors": errors,
        "notes": f"Table rendered, {row_count} rows visible after scroll",
    })

    # --- Example: multi-step form wizard ---
    page.goto("http://localhost:3000/reports/generate", wait_until="networkidle")
    msf = MultiStepFormHandler(page, artifacts_dir=SCREENSHOTS)
    success = msf.execute_steps([
        FormStep(
            name="select_template",
            action=lambda p: p.click("text=警情专报"),
            verify=lambda p: p.locator(".selected-template, [class*='selected']").is_visible(),
        ),
        FormStep(
            name="set_date_range",
            action=lambda p: (p.click('input[placeholder*="开始"]'), p.click("text=近7天")),
            verify=lambda p: p.locator(".date-range-display, .selected-range").count() > 0,
        ),
        FormStep(
            name="submit",
            action=lambda p: p.click("button:has-text('生成报告')"),
            verify=lambda p: p.locator(".ant-alert-success, [class*='success']").is_visible(),
            timeout_ms=60000,
        ),
    ])
    results.append({
        "url": "/reports/generate",
        "status": "PASS" if success else "FAIL",
        "notes": msf.get_summary(),
    })

    browser.close()

# --- Generate report ---
from src.report.coverage_report import CoverageReporter
reporter = CoverageReporter(sitemap, results, artifacts_dir=ARTIFACTS)
report_md = reporter.generate()
Path(f"{ARTIFACTS}/report.md").write_text(report_md)
print(report_md)
```

---

## Robust Interaction Reference

When the crawler or checklist execution hits complex UI patterns, use these built-in handlers:

### Modal / Dialog
```python
from src.interact import ModalHandler
mh = ModalHandler()

# Handle browser confirm() dialog triggered by an action
dialog_msg = mh.handle_modal(page, lambda: page.click("button.delete"), auto_accept=True)

# Close an Ant Design / Material DOM modal
mh.close_dom_modal(page)
```

### Infinite Scroll / Lazy Load
```python
from src.interact import ScrollHelper
sh = ScrollHelper()

count = sh.scroll_until_stable(page, "tr[data-row-key], .list-item", max_scrolls=15)
```

### Shadow DOM
```python
from src.interact import ShadowDomHandler
sdh = ShadowDomHandler()

# Click inside shadow DOM
sdh.click_in_shadow_dom(page, "my-app", "paper-button.primary")

# Get shadow DOM HTML
html = sdh.get_shadow_dom_html(page, "my-app")
```

### iframe
```python
from src.interact import IframeHandler
ih = IframeHandler()

# List all iframes
iframes = ih.get_all_iframes(page)

# Act inside an iframe
ih.interact_in_iframe(page, "iframe[name='content']", lambda fp: fp.click("text=Submit"))
```

### Multi-step Form / Wizard
```python
from src.interact import MultiStepFormHandler, FormStep
msf = MultiStepFormHandler(page)
msf.execute_steps([
    FormStep(name="step1", action=lambda p: p.click("text=Next"), verify=lambda p: p.locator(".step-2").is_visible()),
    FormStep(name="step2", action=lambda p: p.click("text=Submit"), verify=lambda p: p.locator(".success").is_visible()),
])
```

---

## Config Override

Create `webapp-autotest.config.json` in project root to override defaults:

```json
{
  "base_url": "http://localhost:13000",
  "auth": {
    "enabled": true,
    "login_url": "/login",
    "username_field": "input[type='text'], input[placeholder*='用户']",
    "password_field": "input[type='password']",
    "submit_button": "button[type='submit']",
    "credentials": {
      "username": "admin",
      "password": "Admin123"
    }
  },
  "crawl": {
    "max_depth": 3,
    "max_pages": 200
  },
  "output": {
    "artifacts_dir": "test-artifacts/webapp-autotest"
  }
}
```

---

## Decision Tree

```
User asks to test a webapp
│
├─ Server already running?
│   ├─ No → Use scripts/with_server.py to start it first
│   └─ Yes → Continue
│
├─ Tech stack known?
│   ├─ Next.js/Rails/Django → Run static analysis first (fast)
│   └─ Unknown / SPA → Skip to Playwright crawl
│
├─ Needs auth?
│   ├─ Yes → Crawl with credentials injected
│   └─ No → Anonymous crawl
│
└─ Run 3 phases in order:
    Phase 1: discover → sitemap.json
    Phase 2: plan → checklist.md
    Phase 3: execute → report.md
```

---

## Constraints (enforced by this skill)

- ✅ **Always discover routes before testing** — never test randomly from a single URL
- ✅ **Always generate a checklist** — it is the gate for Phase 3
- ✅ **Always collect evidence** — screenshot + console errors per page
- ✅ **Always handle complex patterns** — use ModalHandler/ScrollHelper/IframeHandler/ShadowDomHandler
- ✅ **Always report honestly** — SKIP requires an explicit reason, blank items are not allowed
- ❌ **Never declare "all tests pass"** without a completed checklist with evidence
- ❌ **Never skip Critical items** without documenting why
