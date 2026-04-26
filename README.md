# webapp-autotest

**The AI agent-native webapp testing framework.**

Stop writing test scripts. Let the AI discover your routes, generate a test checklist, exercise every page and interaction, and report what it actually tested — with evidence.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## The Problem

LLMs (Claude Code, Cursor, Copilot) test webapps randomly, by feel. They navigate a few pages, click a couple buttons, and declare "all tests pass." The coverage is shallow, untested routes are invisible, and there's no accountability for what was — and wasn't — tested.

**You deserve the same rigor from AI testing that you get from human QA.**

---

## The Solution

`webapp-autotest` is a skill for AI coding agents that:

1. **Discovers** — Crawls your entire webapp (routes, links, forms, API endpoints) before testing starts
2. **Plans** — Generates a structured test checklist organized by priority
3. **Tests** — Exercises every page, form, and interaction with built-in handlers for complex UI patterns
4. **Reports** — Produces a coverage report with evidence: screenshots, console logs, and explicit skip reasons

---

## Quick Start

```bash
# Install dependencies
pip install playwright && playwright install chromium

# Clone the skill
git clone https://github.com/ai-autotest/webapp-autotest.git
cd webapp-autotest

# Run the full 3-phase workflow on your app at http://localhost:3000
python -c "
import asyncio
from src.discover import detect_tech_stack, crawl_site, analyze_nextjs_pages, SiteMap
from src.checklist import ChecklistGenerator
from pathlib import Path

base_url = 'http://localhost:3000'
sitemap = crawl_site(base_url, max_depth=3)
checklist = ChecklistGenerator(sitemap).generate()
Path('checklist.md').write_text(checklist)
print('checklist.md generated')
print(f'Discovered {len(sitemap.routes)} routes')
"
```

Or use it as a **Claude Code skill**:

```
/skill webapp-autotest
> Test my webapp at http://localhost:3000
```

---

## Three-Phase Workflow

### Phase 1: Discover

```python
from src.discover import crawl_site, detect_tech_stack, analyze_nextjs_pages

# Auto-detect tech stack and discover routes
sitemap = crawl_site("http://localhost:3000", max_depth=3)
```

Discovers: pages, API routes, forms, links, dynamic segments, auth requirements.

### Phase 2: Plan

```python
from src.checklist import ChecklistGenerator

checklist_md = ChecklistGenerator(sitemap).generate()
# Every item requires PASS / FAIL / SKIP — no blanks allowed
```

Generates: prioritized checklist (Critical → Standard → Edge), strategy suggestions per route.

### Phase 3: Execute

```python
from src.interact import ModalHandler, ScrollHelper, MultiStepFormHandler, FormStep

mh = ModalHandler()
sh = ScrollHelper()
# ... test each checklist item with evidence collection
```

Handles: modals, infinite scroll, shadow DOM, iframes, multi-step forms — automatically.

### Output: Coverage Report

```python
from src.report import CoverageReporter

report = CoverageReporter(sitemap, results).generate()
# Coverage %, PASS/FAIL/SKIP per route, console errors, recommendations
```

---

## Features

### Route Discovery
- Multi-strategy cascade: static analysis (Next.js/Rails/Django) + sitemap.xml + Playwright crawler
- Discovers pages, API routes, forms, links, and dynamic segments
- Auth-aware: logs in automatically, then crawls authenticated routes
- Works on any tech stack — Next.js, Rails, Django, Laravel, plain HTML

### Test Checklist
- Auto-generated before testing begins
- Routes organized into 3 priority tiers (Critical / Standard / Edge)
- Every item requires either a PASS/FAIL result or an explicit SKIP reason
- Forms tested with all field types: text, password, select, checkbox, file upload

### Robust Interaction Handlers
- **Modal/Dialog** — Browser dialogs (alert/confirm) + DOM modals (Ant Design, Material, Bootstrap)
- **Shadow DOM** — Traverse shadow roots in Web Components, Stencil, Lit
- **Infinite Scroll** — Auto-scroll until content stabilizes
- **Multi-step Forms** — Wizards, multi-page forms, stateful flows
- **iframes** — Nested frames, srcdoc, sandboxed iframes

### Coverage Report
- Total routes discovered vs. tested vs. skipped
- Per-route PASS/FAIL/SKIP with evidence (screenshot paths, console errors)
- Console error inventory per page
- Interaction pattern success rates
- Explicit documentation of untested routes with manual testing recommendations

---

## Architecture

```
webapp-autotest/
├── SKILL.md                   # Claude Code skill (Markdown + tool definitions)
├── src/
│   ├── discover/              # Route discovery engines
│   │   ├── models.py          # Data models (SiteMap, DiscoveredRoute)
│   │   ├── crawler.py         # Playwright-based site crawler
│   │   ├── static_analyzer.py # Read route definitions from source
│   │   ├── sitemap_parser.py  # sitemap.xml + robots.txt
│   │   └── tech_stack_detector.py
│   ├── interact/              # Complex UI pattern handlers
│   │   ├── modal_handler.py   # Dialogs + DOM modals
│   │   ├── scroll_helper.py   # Infinite scroll / lazy load
│   │   ├── shadow_dom_handler.py
│   │   ├── iframe_handler.py
│   │   └── multi_step_form.py
│   ├── checklist/            # Test plan generation
│   │   └── generator.py
│   └── report/               # Coverage report generation
│       └── coverage_report.py
├── scripts/
│   └── with_server.py        # Server lifecycle manager
├── config/
│   └── default_config.json    # Configurable defaults
└── examples/                  # Usage examples
```

---

## Comparison

| Feature | webapp-autotest | Playwright Test | Cypress | Browser Use / Stagehand |
|---------|----------------|-----------------|---------|--------------------------|
| AI-native (LLM-driven) | Yes | No | No | Partial |
| Auto-route discovery | Yes | No | No | No |
| Pre-test checklist | Yes | No | No | No |
| Coverage report | Yes | Partial | No | No |
| No test script writing | Yes | No | No | Yes |
| Tech-stack agnostic | Yes | Yes | Yes | Yes |
| Shadow DOM support | Yes | Yes | No | Yes |
| Multi-step form handler | Yes | No | No | Partial |

**The unique angle**: `webapp-autotest` is not a test framework — it is an **AI agent's testing methodology**. It brings the discipline of QA engineering (discovery, planning, evidence, reporting) to LLM-driven testing, solving the accountability gap that makes AI testing unreliable today.

---

## Configuration

Create `webapp-autotest.config.json` in your project root:

```json
{
  "base_url": "http://localhost:3000",
  "auth": {
    "enabled": true,
    "login_url": "/login",
    "credentials": {
      "username": "admin",
      "password": "password123"
    }
  },
  "discovery": {
    "max_depth": 3,
    "max_pages": 200
  }
}
```

---

## Contributing

Contributions welcome! Issues, PRs, and feature requests appreciated.

- 🐛 Bug reports → GitHub Issues
- 🔧 PRs → fork and submit
- 📖 Docs → improve SKILL.md or this README

License: MIT
