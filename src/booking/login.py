from __future__ import annotations

import logging

from playwright.async_api import Page

LOGGER = logging.getLogger(__name__)

USERNAME_INPUT_SELECTOR = "TODO: fill username input selector"
PASSWORD_INPUT_SELECTOR = "TODO: fill password input selector"
SUBMIT_BUTTON_SELECTOR = "TODO: fill login submit selector"
LOGIN_SUCCESS_SELECTOR = "TODO: fill selector that appears after login"


async def perform_login(page: Page, username: str, password: str) -> bool:
    """Authenticate against the ticketing site (update selectors first)."""

    if "TODO" in USERNAME_INPUT_SELECTOR or "TODO" in PASSWORD_INPUT_SELECTOR:
        raise RuntimeError("Update booking/login.py selectors before enabling auto-book")

    await page.fill(USERNAME_INPUT_SELECTOR, username)
    await page.fill(PASSWORD_INPUT_SELECTOR, password)
    await page.click(SUBMIT_BUTTON_SELECTOR)
    await page.wait_for_timeout(2_000)
    try:
        await page.wait_for_selector(LOGIN_SUCCESS_SELECTOR, timeout=15_000)
        LOGGER.info("Login successful")
        return True
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Login failed: %s", exc)
        return False
