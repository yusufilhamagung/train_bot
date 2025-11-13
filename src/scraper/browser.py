from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator, Tuple

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

LOGGER = logging.getLogger(__name__)


async def create_page(*, headless: bool = False, slow_mo_ms: int | None = None) -> Tuple[Playwright, Browser, BrowserContext, Page]:
    """Launch Playwright Chromium and return a ready page."""

    playwright = await async_playwright().start()
    launch_kwargs = {"headless": headless}
    if slow_mo_ms:
        launch_kwargs["slow_mo"] = slow_mo_ms
    browser = await playwright.chromium.launch(**launch_kwargs)
    context = await browser.new_context()
    page = await context.new_page()
    return playwright, browser, context, page


async def close_browser(playwright: Playwright, browser: Browser, context: BrowserContext) -> None:
    """Close all browser resources."""

    try:
        await context.close()
    finally:
        try:
            await browser.close()
        finally:
            await playwright.stop()


@asynccontextmanager
async def browser_session(*, headless: bool = True, slow_mo_ms: int | None = None) -> AsyncIterator[Page]:
    """Yield a Playwright page within a managed session."""

    playwright, browser, context, page = await create_page(headless=headless, slow_mo_ms=slow_mo_ms)
    try:
        yield page
    finally:
        await close_browser(playwright, browser, context)
