"""Generate a coverage report from test execution results."""
import json
from datetime import datetime
from pathlib import Path
from src.discover import SiteMap, Priority


class CoverageReporter:
    """
    Generates a markdown coverage report from sitemap + test results.

    results format: list of dicts with keys:
      - url: str
      - status: "PASS" | "FAIL" | "SKIP"
      - screenshot: str (optional)
      - console_errors: list[str] (optional)
      - notes: str (optional)
      - step_results: list[dict] (optional, from MultiStepFormHandler)
    """

    def __init__(self, sitemap: SiteMap, results: list[dict], artifacts_dir: str = "test-artifacts/webapp-autotest"):
        self.sitemap = sitemap
        self.results = {self._normalize_url(r["url"]): r for r in results}
        self.artifacts_dir = artifacts_dir

    def generate(self) -> str:
        stats = self._compute_stats()
        sections = []
        sections.append(self._header(stats))
        sections.append("")
        sections.append(self._summary_table(stats))
        sections.append("")
        sections.append(self._detailed_results(stats))
        sections.append("")
        sections.append(self._console_errors())
        sections.append("")
        sections.append(self._interaction_pattern_summary())
        sections.append("")
        sections.append(self._skipped_routes())
        sections.append("")
        sections.append(self._recommendations(stats))
        return "\n".join(sections)

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        url = url.split("#")[0].rstrip("/")
        return url or "/"

    def _compute_stats(self) -> dict:
        total = len(self.sitemap.routes)
        tested = sum(
            1 for r in self.sitemap.routes
            if self._normalize_url(r.url) in [self._normalize_url(x) for x in self.results.keys()]
        )
        passed = sum(1 for x in self.results.values() if x.get("status") == "PASS")
        failed = sum(1 for x in self.results.values() if x.get("status") == "FAIL")
        skipped = sum(1 for x in self.results.values() if x.get("status") == "SKIP")

        console_errors = []
        for x in self.results.values():
            console_errors.extend(x.get("console_errors", []))

        return {
            "total": total,
            "tested": tested,
            "untested": total - tested,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "coverage_pct": round(tested / total * 100, 1) if total else 0,
            "console_error_count": len(console_errors),
            "console_errors": console_errors,
        }

    def _header(self, stats: dict) -> str:
        verdict = "✅ PASS — No failures detected" if stats["failed"] == 0 else f"⚠️ ISSUES — {stats['failed']} failure(s) detected"
        return f"""# webapp-autotest Coverage Report

**Tested**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Base URL**: {self.sitemap.base_url}
**Verdict**: {verdict}
"""

    def _summary_table(self, stats: dict) -> str:
        return f"""## Executive Summary

| Metric | Result |
|--------|--------|
| Total Routes Discovered | {stats['total']} |
| Routes Tested | {stats['tested']} |
| Routes Not Tested | {stats['untested']} |
| PASS | {stats['passed']} |
| FAIL | {stats['failed']} |
| SKIP | {stats['skipped']} |
| **Coverage** | **{stats['coverage_pct']}%** |
| Console Errors Found | {stats['console_error_count']} |
"""

    def _detailed_results(self, stats: dict) -> str:
        lines = ["## Detailed Results", ""]
        routes = sorted(self.sitemap.routes, key=lambda r: (r.priority.value, r.url))

        for r in routes:
            norm_url = self._normalize_url(r.url)
            result = self.results.get(norm_url)

            icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(result.get("status") if result else "", "❓")

            if not result:
                lines.append(f"### `{norm_url or '/'}` — ❓ NOT TESTED")
                lines.append(f"  - **Result**: NOT TESTED")
                lines.append(f"  - **Recommendation**: Add to checklist execution")
                lines.append("")
                continue

            status = result.get("status", "UNKNOWN")
            icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(status, "❓")
            notes = result.get("notes", "")
            screenshot = result.get("screenshot", "")
            errors = result.get("console_errors", [])
            step_results = result.get("step_results", [])

            lines.append(f"### `{norm_url or '/'}` — {icon} {status}")

            if screenshot:
                lines.append(f"  - **Screenshot**: `{screenshot}`")
            if notes:
                lines.append(f"  - **Notes**: {notes}")

            if errors:
                lines.append(f"  - **Console Errors** ({len(errors)}):")
                for err in errors[:5]:
                    lines.append("    ```\n    " + err + "\n    ```")

            if step_results:
                lines.append("  - **Form Steps**:")
                for step in step_results:
                    step_icon = {"pass": "✅", "fail": "❌", "skipped": "⏭️"}.get(step.get("status", ""), "❓")
                    name = step.get("name", "?")
                    status = step.get("status", "?")
                    err = step.get("error", "")
                    err_part = f" — {err}" if err else ""
                    lines.append(f"    - {step_icon} `{name}`: {status}{err_part}")

            lines.append("")
        return "\n".join(lines)

    def _console_errors(self) -> str:
        all_errors = []
        for x in self.results.values():
            all_errors.extend(x.get("console_errors", []))

        if not all_errors:
            return ""

        lines = ["## Console Errors", ""]
        # Group by page
        error_by_page = {}
        for x in self.results.values():
            for err in x.get("console_errors", []):
                url = x.get("url", "unknown")
                error_by_page.setdefault(url, []).append(err)

        for url, errors in error_by_page.items():
            lines.append(f"### `{url}`")
            for err in errors:
                lines.append("  ```\n  " + err + "\n  ```")
            lines.append("")
        return "\n".join(lines)

    def _interaction_pattern_summary(self) -> str:
        # Count interaction patterns used
        patterns = {
            "Modal/Dialog": 0,
            "Infinite Scroll": 0,
            "Shadow DOM": 0,
            "iframe": 0,
            "Multi-step Form": 0,
        }
        for x in self.results.values():
            notes = str(x.get("notes", "")).lower()
            if "modal" in notes or "dialog" in notes:
                patterns["Modal/Dialog"] += 1
            if "scroll" in notes:
                patterns["Infinite Scroll"] += 1
            if "shadow" in notes:
                patterns["Shadow DOM"] += 1
            if "iframe" in notes:
                patterns["iframe"] += 1
            if "step" in notes or "wizard" in notes:
                patterns["Multi-step Form"] += 1

        if all(v == 0 for v in patterns.values()):
            return ""

        lines = ["## Interaction Pattern Usage", ""]
        lines.append("| Pattern | Times Used |")
        lines.append("|---------|-----------|")
        for name, count in patterns.items():
            if count > 0:
                lines.append(f"| {name} | {count} |")
        return "\n".join(lines)

    def _skipped_routes(self) -> str:
        untested = [
            r for r in self.sitemap.routes
            if self._normalize_url(r.url) not in [self._normalize_url(x) for x in self.results.keys()]
        ]
        if not untested:
            return ""

        lines = ["## Untested Routes", ""]
        lines.append("| Route | Priority | Recommended Manual Action |")
        lines.append("|-------|----------|--------------------------|")
        for r in untested:
            action = self._manual_action(r)
            lines.append(f"| `{self._normalize_url(r.url) or '/'}` | P{r.priority.value} | {action} |")
        return "\n".join(lines)

    def _manual_action(self, route) -> str:
        if route.params:
            return f"Requires valid `{', '.join(route.params)}` ID — test with known record"
        if route.route_type.value == "api":
            return "API endpoint — test via frontend UI or Postman"
        return "Test with typical user workflow"

    def _recommendations(self, stats: dict) -> str:
        lines = ["## Recommendations", ""]
        if stats["failed"] > 0:
            lines.append(f"1. **Fix {stats['failed']} failing route(s)** — see detailed results above")
        if stats["console_error_count"] > 0:
            lines.append(f"2. **Address {stats['console_error_count']} console error(s)** — check browser console for details")
        if stats["untested"] > 0:
            lines.append(f"3. **Test untested routes** ({stats['untested']} remaining) — add to checklist and re-run")
        if stats["coverage_pct"] < 80:
            lines.append(f"4. ⚠️ Coverage at {stats['coverage_pct']}% — consider increasing crawl depth or adding authenticated routes")
        if stats["failed"] == 0 and stats["console_error_count"] == 0 and stats["coverage_pct"] >= 80:
            lines.append("✅ All tested routes pass with no console errors. Coverage is acceptable.")
        lines.append("")
        return "\n".join(lines)
