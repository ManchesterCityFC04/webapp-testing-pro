"""Generate a structured test checklist from a SiteMap."""
from datetime import datetime
from src.discover import DiscoveredRoute, Priority, RouteType, SiteMap


# Keywords that map URL patterns to priority / test strategy
AUTH_KEYWORDS = ["login", "signin", "auth", "logout", "session"]
CRITICAL_KEYWORDS = ["dashboard", "statistics", "incidents", "reports", "admin", "analysis", "overview"]
FORM_KEYWORDS = ["create", "new", "add", "edit", "setting", "config", "profile"]
EDGE_KEYWORDS = ["detail", "[id]", "[pk]", "[slug]"]


class ChecklistGenerator:
    """Generates a markdown test checklist from a SiteMap."""

    def __init__(self, sitemap: SiteMap):
        self.sitemap = sitemap

    def generate(self) -> str:
        sections = []
        sections.append(self._header())
        sections.append(self._coverage_summary())
        sections.append("")
        sections.append(self._phase_a_critical())
        sections.append("")
        sections.append(self._phase_b_standard())
        sections.append("")
        sections.append(self._phase_c_edge())
        sections.append("")
        sections.append(self._known_limitations())
        sections.append("")
        sections.append(self._footer())
        return "\n".join(sections)

    def _header(self) -> str:
        total = len(self.sitemap.routes)
        pages = len(self.sitemap.pages)
        apis = len(self.sitemap.apis)
        strategies = ", ".join(self.sitemap.discovery_strategies_used) if self.sitemap.discovery_strategies_used else "unknown"
        return f"""# webapp-autotest Checklist

**Base URL**: {self.sitemap.base_url}
**Discovered**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Total Routes Discovered**: {total} ({pages} pages, {apis} API routes)
**Discovery Strategies**: {strategies}

> ⚠️ **Every item requires a result: PASS / FAIL / SKIP. Blank items are NOT allowed.**
> SKIP items must include a specific reason in **Skip reason:** field.
"""

    def _coverage_summary(self) -> str:
        stats = self.sitemap.coverage_stats
        return f"""## Coverage Summary

| Category | Total |
|----------|-------|
| Pages (GET) | {stats.get('pages', len(self.sitemap.pages))} |
| API Routes | {stats.get('apis', len(self.sitemap.apis))} |
| Total Routes | {stats.get('total', len(self.sitemap.routes))} |

"""

    def _phase_a_critical(self) -> str:
        routes = [r for r in self.sitemap.routes if r.priority == Priority.CRITICAL or r.route_type == RouteType.API and "auth" in r.url.lower()]
        if not routes:
            routes = [r for r in self.sitemap.routes if any(k in r.url.lower() for k in CRITICAL_KEYWORDS + AUTH_KEYWORDS)]
        return self._section("Phase A: Critical (Priority 1)", routes, """
> Must test: authentication flows, primary business pages, forms that create/modify data.
> Every item below must have a result — PASS, FAIL, or SKIP with reason.
""")

    def _phase_b_standard(self) -> str:
        routes = [r for r in self.sitemap.routes if r.priority == Priority.STANDARD]
        routes = [r for r in routes if r not in [x for x in self.sitemap.routes if x.priority == Priority.CRITICAL]]
        return self._section("Phase B: Standard (Priority 2)", routes[:30], """
> Standard pages: list views, read-only pages, informational pages.
> Items marked SKIP should note what manual testing would cover.
""")

    def _phase_c_edge(self) -> str:
        routes = [r for r in self.sitemap.routes if r.priority == Priority.EDGE]
        # Also include dynamic routes
        dynamic = [r for r in self.sitemap.routes if r.params]
        routes = list({r.url: r for r in routes + dynamic}.values())
        return self._section("Phase C: Edge Cases (Priority 3)", routes[:15], """
> Dynamic routes with IDs/params, error pages, unauthenticated access tests.
> Some may require specific data to exist first.
""")

    def _known_limitations(self) -> str:
        non_testable = [
            r for r in self.sitemap.routes
            if r.route_type == RouteType.STATIC
            or "tiles" in r.url.lower()
            or r.route_type == RouteType.API
            and any(k in r.url.lower() for k in ["health", "metrics", "internal"])
        ]
        if not non_testable:
            return ""
        lines = ["## Known Limitations (pre-marked non-testable)", ""]
        lines.append("These routes are not testable via browser and do not count against coverage:")
        lines.append("")
        for r in non_testable:
            reason = "API/internal endpoint" if r.route_type == RouteType.API else "Static asset"
            lines.append(f"- `{r.url}` — {reason}")
        return "\n".join(lines)

    def _section(self, title: str, routes: list[DiscoveredRoute], note: str = "") -> str:
        if not routes:
            return f"## {title}\n\n*(No routes found in this category)*\n"
        lines = [f"## {title}", note, ""]
        for i, r in enumerate(routes, 1):
            base = r.url.replace(self.sitemap.base_url, "") or "/"
            route_type_label = r.route_type.value.upper()
            form_count = len(r.forms)
            form_info = f" | **{form_count} form(s)**" if form_count > 0 else ""

            # Suggest test strategy
            strategy = self._suggest_strategy(r)

            lines.append(f"### A{i} `{base}` — {route_type_label}{form_info}")
            lines.append(f"- [ ] **URL**: `{r.url}`")
            if r.params:
                lines.append(f"  - **Params**: `{r.params}`")
            if form_count > 0:
                for fi, form in enumerate(r.forms):
                    method = form.method.upper()
                    field_names = [f.name for f in form.fields if f.name]
                    lines.append(f"  - **Form {fi+1}**: `{method} {form.action}` — fields: `{', '.join(field_names) or 'auto-detect'}`")
            lines.append(f"  - **Strategy**: {strategy}")
            lines.append(f"  - **Evidence**: Screenshot at `{{{{artifacts_dir}}}}/screenshots/{self._safe_name(base)}.png`")
            lines.append(f"  - **Result**: PASS / FAIL / SKIP")
            lines.append(f"  - **Skip reason**: _______________")
            lines.append("")
        return "\n".join(lines)

    def _suggest_strategy(self, route: DiscoveredRoute) -> str:
        """Suggest a test strategy based on route characteristics."""
        url = route.url.lower()

        if any(k in url for k in AUTH_KEYWORDS):
            return "`ModalHandler.handle_modal()` + auto-login flow; verify redirect to dashboard"
        if route.params:
            return "`navigate_and_wait()` + verify page content renders; param = `{{param}}` placeholder"
        if len(route.forms) > 0:
            return "`ScrollHelper.scroll_until_stable()` for list; `MultiStepFormHandler()` for forms"
        if any(k in url for k in FORM_KEYWORDS):
            return "Fill form fields; submit; verify success/error state"
        return "`navigate_and_wait()`; verify key element visible (title, table, chart)"

    def _safe_name(self, url: str) -> str:
        """Convert URL to safe filename."""
        return url.strip("/").replace("/", "_").replace("[", "").replace("]", "").replace("?", "_") or "root"

    def _footer(self) -> str:
        return f"""---

**Generated by**: webapp-autotest v1.0
**Next step**: Run Phase 3 Execute, then `src/report/coverage_report.py` to produce `report.md`
"""
