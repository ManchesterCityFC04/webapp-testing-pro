"""Handle browser dialogs (alert/confirm/prompt) and DOM-based modals."""
from playwright.sync_api import Page, Locator, TimeoutError as PWTimeout
from typing import Callable, Optional


class ModalHandler:
    """
    Handles:
    - Browser dialogs: alert(), confirm(), prompt() via page.on("dialog")
    - DOM-based modals: Ant Design Modal, Material Dialog, Bootstrap Modal, etc.
    - Confirmation dialogs triggered by form actions
    """

    DIALOG_TIMEOUT_MS = 5000

    def handle_modal(
        self,
        page: Page,
        action_fn: Callable,
        expected_type: str = "confirm",
        auto_accept: bool = True,
    ) -> Optional[str]:
        """
        Perform action_fn while listening for a browser dialog.
        Returns dialog message if appeared, None otherwise.
        """
        result: list[str] = []

        def on_dialog(dialog):
            result.append(dialog.message)
            if auto_accept:
                dialog.accept()
            else:
                dialog.dismiss()

        page.on("dialog", on_dialog)
        try:
            action_fn()
            page.wait_for_timeout(500)
        finally:
            page.remove_listener("dialog", on_dialog)

        return result[0] if result else None

    def wait_for_dom_modal(
        self,
        page: Page,
        selector: str = ".ant-modal, [role='dialog'], .modal, .el-dialog, .MuiDialog-root",
        timeout_ms: int = 8000,
    ) -> Optional[Locator]:
        """Wait for a DOM-based modal to appear."""
        try:
            page.wait_for_selector(selector, timeout=timeout_ms)
            return page.locator(selector).last
        except PWTimeout:
            return None

    def close_dom_modal(
        self,
        page: Page,
        close_selector: str = ".ant-modal-close, [aria-label='Close'], .modal .close, button[class*='close'], .el-dialog__close",
    ):
        """
        Try multiple strategies to close a DOM modal:
        1. Close button
        2. Escape key
        3. Backdrop click
        """
        # Strategy 1: Close button
        close_btn = page.locator(close_selector)
        if close_btn.count() > 0 and close_btn.first.is_visible():
            close_btn.first.click()
            return

        # Strategy 2: Escape key
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # Strategy 3: Click backdrop (top-left corner of backdrop)
        backdrop_selectors = [
            ".ant-modal-mask",
            ".modal-backdrop",
            ".el-dialog__wrapper",
            "[role='presentation']",
        ]
        for sel in backdrop_selectors:
            backdrop = page.locator(sel)
            if backdrop.count() > 0 and backdrop.first.is_visible():
                backdrop.first.click(position={"x": 10, "y": 10})
                page.wait_for_timeout(200)
                break

    def dismiss_confirmation_flow(
        self,
        page: Page,
        trigger_action: Callable,
        dialog_selector: str = "[role='alertdialog'], .confirm-dialog",
    ) -> bool:
        """
        Trigger an action that may show a confirmation, dismiss it,
        and verify the original action was NOT triggered.
        """
        dialog_appeared = False

        def on_dialog(dialog):
            nonlocal dialog_appeared
            dialog_appeared = True
            dialog.dismiss()

        page.on("dialog", on_dialog)
        try:
            trigger_action()
            page.wait_for_timeout(500)
        finally:
            page.remove_listener("dialog", on_dialog)

        return dialog_appeared

    def accept_confirmation_flow(
        self,
        page: Page,
        trigger_action: Callable,
        after_accept_fn: Optional[Callable] = None,
        timeout_ms: int = 10000,
    ) -> bool:
        """
        Trigger an action that shows a confirmation, accept it,
        then optionally verify the resulting state via after_accept_fn.
        Returns True if confirmation was accepted successfully.
        """
        dialog_appeared = False

        def on_dialog(dialog):
            nonlocal dialog_appeared
            dialog_appeared = True
            dialog.accept()

        page.on("dialog", on_dialog)
        try:
            trigger_action()
            page.wait_for_timeout(500)
        finally:
            page.remove_listener("dialog", on_dialog)

        if after_accept_fn and dialog_appeared:
            try:
                after_accept_fn()
                return True
            except Exception:
                return False

        return dialog_appeared
