from __future__ import annotations

import logging
import os

from playwright.async_api import Page

from ..config.settings import Settings
from ..models.ticket import TicketOption
from ..scraper.browser import create_page, close_browser
from .login import perform_login

LOGGER = logging.getLogger(__name__)

BOOKING_TRIGGER_SELECTOR = "TODO: fill selector that opens booking flow"
PASSENGER_NAME_SELECTOR = "TODO: fill passenger name input selector"
PASSENGER_ID_SELECTOR = "TODO: fill passenger id input selector"
PASSENGER_BIRTHDATE_SELECTOR = "TODO: fill passenger birth date selector"
CONTINUE_BUTTON_SELECTOR = "TODO: fill selector for continue button"
PAYMENT_SECTION_SELECTOR = "TODO: fill selector that indicates payment page"


async def maybe_book_ticket(ticket: TicketOption, settings: Settings, *, headless: bool | None = None) -> bool:
    """Safely attempt the booking flow up to the payment page."""

    if not settings.auto_book_enabled:
        LOGGER.debug("Auto-book skipped; AUTO_BOOK_ENABLED is false")
        return False

    username = os.getenv("TICKET_SITE_USERNAME")
    password = os.getenv("TICKET_SITE_PASSWORD")
    if not username or not password:
        LOGGER.warning("TICKET_SITE_USERNAME/PASSWORD missing; aborting auto-book")
        return False

    resolved_headless = settings.headless if headless is None else headless
    playwright, browser, context, page = await create_page(headless=resolved_headless)
    try:
        await page.goto(settings.base_url, wait_until="domcontentloaded")
        if not await perform_login(page, username, password):
            return False
        await _open_booking(page)
        await _fill_passengers(page, settings)
        await _advance_to_payment(page)
        LOGGER.info("Reached payment screen for %s; stopping as safeguard", ticket.short_label())
        return True
    finally:
        await close_browser(playwright, browser, context)


async def _open_booking(page: Page) -> None:
    if "TODO" in BOOKING_TRIGGER_SELECTOR:
        raise RuntimeError("Update booking selectors before enabling auto-book")
    await page.click(BOOKING_TRIGGER_SELECTOR)
    await page.wait_for_timeout(1_000)


async def _fill_passengers(page: Page, settings: Settings) -> None:
    if not settings.passenger_profiles:
        LOGGER.warning("No passenger profiles loaded; PASSENGERS_FILE is required for auto-book")
        return
    for passenger in settings.passenger_profiles:
        await page.fill(PASSENGER_NAME_SELECTOR, passenger.full_name)
        await page.fill(PASSENGER_ID_SELECTOR, passenger.national_id)
        await page.fill(PASSENGER_BIRTHDATE_SELECTOR, passenger.birth_date.strftime("%Y-%m-%d"))


async def _advance_to_payment(page: Page) -> None:
    await page.click(CONTINUE_BUTTON_SELECTOR)
    await page.wait_for_selector(PAYMENT_SECTION_SELECTOR, timeout=30_000)
