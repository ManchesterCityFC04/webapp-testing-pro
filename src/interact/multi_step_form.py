"""Handle multi-step wizards, multi-page forms, and stateful form flows."""
from playwright.sync_api import Page
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class FormStep:
    name: str
    action: Callable[[Page], None]
    verify: Optional[Callable[[Page], bool]] = None
    timeout_ms: int = 10000
    screenshot_on_error: bool = True


@dataclass
class StepResult:
    name: str
    status: str = "pending"  # "pass" | "fail" | "skipped"
    error: Optional[str] = None
    screenshot_path: Optional[str] = None


class MultiStepFormHandler:
    """
    Handles multi-step wizards and stateful form flows.

    Example usage:
        handler = MultiStepFormHandler(page)
        success = handler.execute_steps([
            FormStep(
                name="select_template",
                action=lambda p: p.click("text=警情专报"),
                verify=lambda p: p.locator(".selected-template").is_visible(),
            ),
            FormStep(
                name="submit",
                action=lambda p: p.click("button:has-text('生成报告')"),
                verify=lambda p: p.locator(".ant-alert-success").is_visible(),
                timeout_ms=60000,
            ),
        ])
    """

    def __init__(self, page: Page, artifacts_dir: str = "test-artifacts/webapp-autotest/screenshots"):
        self.page = page
        self.artifacts_dir = artifacts_dir
        self.results: list[StepResult] = []

    def execute_steps(self, steps: list[FormStep]) -> bool:
        """Execute a list of form steps in order. Returns True if all pass."""
        self.results = []

        for step in steps:
            result = StepResult(name=step.name)
            try:
                step.action(self.page)
                self.page.wait_for_timeout(500)  # Let UI update

                if step.verify:
                    verified = step.verify(self.page)
                    if not verified:
                        result.status = "fail"
                        result.error = f"verify() returned False for step '{step.name}'"
                    else:
                        result.status = "pass"
                else:
                    result.status = "pass"

            except Exception as e:
                result.status = "fail"
                result.error = str(e)
                if step.screenshot_on_error:
                    import os
                    os.makedirs(self.artifacts_dir, exist_ok=True)
                    safe_name = step.name.replace(" ", "_").replace("/", "_")
                    path = f"{self.artifacts_dir}/{safe_name}_error.png"
                    self.page.screenshot(path=path, full_page=True)
                    result.screenshot_path = path

            self.results.append(result)

            # Stop on failure unless the step is marked as skippable
            if result.status == "fail" and not step.verify:
                return False

        return all(r.status == "pass" for r in self.results)

    def retry_until_success(
        self,
        action: Callable[[Page], None],
        max_retries: int = 3,
        delay_ms: int = 2000,
    ) -> bool:
        """Retry an action with exponential backoff."""
        import time

        for attempt in range(max_retries):
            try:
                action(self.page)
                return True
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep((delay_ms * (2 ** attempt)) / 1000)
        return False

    def fill_wizard_field(
        self,
        selector: str,
        value: str,
        clear_first: bool = True,
        press_enter: bool = False,
    ):
        """Fill a form field in a wizard, with optional clear and enter."""
        loc = self.page.locator(selector)
        if clear_first:
            loc.clear()
        loc.fill(value)
        if press_enter:
            self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(300)

    def get_summary(self) -> dict:
        """Get a summary dict of all step results."""
        return {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r.status == "pass"),
            "failed": sum(1 for r in self.results if r.status == "fail"),
            "skipped": sum(1 for r in self.results if r.status == "skipped"),
            "steps": [
                {
                    "name": r.name,
                    "status": r.status,
                    "error": r.error,
                    "screenshot": r.screenshot_path,
                }
                for r in self.results
            ],
        }
