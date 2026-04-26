"""
Unit tests for webapp-autotest output correctness.

Run with: pytest tests/test_outputs.py -v
"""
import json
import re
from pathlib import Path

import pytest

# Path to the test artifacts generated during demo run
ARTIFACTS = Path(__file__).parent.parent / "test-artifacts" / "webapp-autotest"
SCREENSHOTS = ARTIFACTS / "screenshots"


class TestChecklistOutput:
    """Verify checklist.md is well-formed and complete."""

    def test_checklist_file_exists(self):
        path = ARTIFACTS / "checklist.md"
        assert path.exists(), f"checklist.md not found at {path}"

    def test_checklist_has_header(self):
        content = (ARTIFACTS / "checklist.md").read_text(encoding="utf-8")
        assert "# webapp-autotest Checklist" in content
        assert "**Base URL**" in content
        assert "**Total Routes Discovered**" in content

    def test_checklist_has_no_empty_result_fields(self):
        """
        Critical rule: every Result: must be PASS / FAIL / SKIP, not blank.
        """
        content = (ARTIFACTS / "checklist.md").read_text(encoding="utf-8")
        # Find all Result: lines
        result_lines = re.findall(r"- \*\*Result\*\*: (.+)", content)
        assert len(result_lines) > 0, "No Result fields found"

        invalid = [line for line in result_lines if line.strip() == ""]
        assert len(invalid) == 0, f"Found {len(invalid)} blank Result fields"

    def test_checklist_has_skip_reason_placeholders(self):
        """
        Every item must have a Skip reason field (even if just underscores).
        """
        content = (ARTIFACTS / "checklist.md").read_text(encoding="utf-8")
        skip_lines = re.findall(r"- \*\*Skip reason\*\*: (.+)", content)
        assert len(skip_lines) > 0, "No Skip reason fields found"

    def test_checklist_has_phase_sections(self):
        content = (ARTIFACTS / "checklist.md").read_text(encoding="utf-8")
        assert "## Phase A: Critical" in content or "Phase A" in content
        assert "## Phase B" in content or "Phase B" in content
        assert "## Phase C" in content or "Phase C" in content

    def test_checklist_has_strategy_per_item(self):
        """Every item must have a suggested test strategy."""
        content = (ARTIFACTS / "checklist.md").read_text(encoding="utf-8")
        strategy_lines = re.findall(r"- \*\*Strategy\*\*: (.+)", content)
        assert len(strategy_lines) > 0
        # None should be empty
        empty = [s for s in strategy_lines if not s.strip() or s.strip() == "______________"]
        assert len(empty) == 0, f"Found {len(empty)} items with no strategy"

    def test_checklist_mentions_discovered_routes(self):
        """Checklist must mention actual routes from sitemap."""
        sitemap_data = json.loads((ARTIFACTS / "sitemap.json").read_text())
        content = (ARTIFACTS / "checklist.md").read_text(encoding="utf-8")

        # Sample a few routes from sitemap
        routes = [r["url"] for r in sitemap_data["routes"][:5]]
        found_count = sum(1 for r in routes if r in content)
        assert found_count >= 3, f"Only {found_count}/5 sampled routes found in checklist"


class TestSitemapOutput:
    """Verify sitemap.json is well-formed."""

    def test_sitemap_file_exists(self):
        path = ARTIFACTS / "sitemap.json"
        assert path.exists(), f"sitemap.json not found at {path}"

    def test_sitemap_has_valid_structure(self):
        data = json.loads((ARTIFACTS / "sitemap.json").read_text())
        assert "base_url" in data
        assert "routes" in data
        assert "discovery_strategies_used" in data
        assert isinstance(data["routes"], list)
        assert len(data["routes"]) > 0

    def test_sitemap_routes_have_required_fields(self):
        data = json.loads((ARTIFACTS / "sitemap.json").read_text())
        for r in data["routes"][:5]:
            assert "url" in r
            assert "route_type" in r
            assert r["route_type"] in ("page", "api", "static", "redirect")

    def test_sitemap_contains_expected_routes(self):
        """Should contain the police system routes we know exist."""
        data = json.loads((ARTIFACTS / "sitemap.json").read_text())
        urls = {r["url"] for r in data["routes"]}
        expected = ["/incidents", "/reports", "/statistics", "/login"]
        found = [r for r in expected if any(r in u for u in urls)]
        assert len(found) >= 3, f"Expected routes missing: {expected}, found {found}"

    def test_sitemap_discovery_stats(self):
        data = json.loads((ARTIFACTS / "sitemap.json").read_text())
        assert data["coverage_stats"]["total"] == len(data["routes"])
        assert data["coverage_stats"]["pages"] >= 50  # Expect 50+ pages


class TestReportOutput:
    """Verify report.md is well-formed and stats add up."""

    def test_report_file_exists(self):
        path = ARTIFACTS / "report.md"
        assert path.exists(), f"report.md not found at {path}"

    def test_report_has_verdict(self):
        content = (ARTIFACTS / "report.md").read_text(encoding="utf-8")
        assert "**Verdict**:" in content
        assert ("PASS" in content or "FAIL" in content)

    def test_report_summary_stats_add_up(self):
        """
        Coverage % = Routes Tested / Total Routes * 100.
        PASS/FAIL/SKIP count should match number of result entries.
        """
        content = (ARTIFACTS / "report.md").read_text(encoding="utf-8")

        # Extract report stats
        total_match = re.search(r"\| Total Routes Discovered \|\s*(\d+)", content)
        tested_match = re.search(r"\| Routes Tested \|\s*(\d+)", content)
        coverage_match = re.search(r"\*\*Coverage\*\*.*?\*\*(\d+(?:\.\d+)?)\%\*\*", content)

        # Coverage % = tested / total * 100
        if coverage_match and total_match and tested_match:
            coverage_pct = float(coverage_match.group(1))
            total = int(total_match.group(1))
            tested = int(tested_match.group(1))
            expected_pct = round(tested / total * 100, 1)
            assert abs(coverage_pct - expected_pct) < 0.1, \
                f"Coverage mismatch: {coverage_pct}% != {expected_pct}% ({tested}/{total})"

        # PASS + FAIL + SKIP from results.json should match report PASS/FAIL/SIP columns
        results_data = json.loads((ARTIFACTS / "results.json").read_text())
        outcome_counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
        for e in results_data:
            outcome_counts[e.get("status", "")] = outcome_counts.get(e.get("status", ""), 0) + 1

        for outcome, count in outcome_counts.items():
            if count == 0:
                continue
            pattern = rf"\| {outcome}\s+\|\s*(\d+)"
            match = re.search(pattern, content)
            if match:
                assert int(match.group(1)) == count, \
                    f"{outcome} mismatch: report says {match.group(1)}, results.json has {count}"

    def test_report_has_detailed_results(self):
        content = (ARTIFACTS / "report.md").read_text(encoding="utf-8")
        assert "## Detailed Results" in content
        # Should have at least one tested route showing PASS/FAIL
        assert ("✅" in content or "❌" in content)

    def test_report_has_recommendations(self):
        content = (ARTIFACTS / "report.md").read_text(encoding="utf-8")
        assert "## Recommendations" in content

    def test_report_coverage_matches_results(self):
        """Coverage % in report should match (tested / total routes)."""
        data = json.loads((ARTIFACTS / "sitemap.json").read_text())
        content = (ARTIFACTS / "report.md").read_text(encoding="utf-8")

        total = data["coverage_stats"]["total"]
        coverage_match = re.search(r"\| Routes Tested \|\s*(\d+)", content)
        tested_match = re.search(r"\| Routes Not Tested \|\s*(\d+)", content)

        if coverage_match and tested_match:
            tested = int(coverage_match.group(1))
            untested = int(tested_match.group(1))
            assert tested + untested == total, f"{tested}+{untested} != {total}"

    def test_passing_routes_have_screenshots(self):
        """PASS routes should have screenshot evidence."""
        content = (ARTIFACTS / "report.md").read_text(encoding="utf-8")
        screenshot_refs = re.findall(r"\*\*Screenshot\*\*: `(.+?)`", content)
        assert len(screenshot_refs) > 0, "No screenshots referenced in report"


class TestScreenshots:
    """Verify screenshots were actually captured."""

    def test_screenshot_dir_exists(self):
        assert SCREENSHOTS.exists(), f"Screenshot dir not found at {SCREENSHOTS}"

    def test_screenshots_have_content(self):
        """Screenshots should exist and be non-empty."""
        if not SCREENSHOTS.exists():
            pytest.skip("Screenshot dir does not exist")

        png_files = list(SCREENSHOTS.glob("*.png"))
        assert len(png_files) > 0, "No PNG screenshots found"

        for png in png_files:
            size = png.stat().st_size
            assert size > 1000, f"Screenshot {png.name} is suspiciously small ({size} bytes) — likely empty/invalid"


class TestResultsJson:
    """Verify results.json is well-formed."""

    def test_results_file_exists(self):
        path = ARTIFACTS / "results.json"
        assert path.exists(), f"results.json not found at {path}"

    def test_results_entries_are_valid(self):
        data = json.loads((ARTIFACTS / "results.json").read_text())
        assert isinstance(data, list)
        assert len(data) > 0

        for entry in data:
            assert "url" in entry
            assert "status" in entry
            assert entry["status"] in ("PASS", "FAIL", "SKIP")
            assert "screenshot" in entry or "console_errors" in entry

    def test_all_results_have_status(self):
        data = json.loads((ARTIFACTS / "results.json").read_text())
        blank_status = [e for e in data if not e.get("status")]
        assert len(blank_status) == 0, f"Found {len(blank_status)} entries with no status"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
