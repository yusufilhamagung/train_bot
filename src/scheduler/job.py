from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List

from ..config.settings import Settings
from ..models.ticket import TicketOption
from ..notifier import email_notifier
from ..notifier.telegram import send_telegram_alert
from ..scraper.search import filter_tickets, format_ticket_table, search_tickets
from ..booking.book import maybe_book_ticket

LOGGER = logging.getLogger(__name__)


async def run_search_once(
    settings: Settings,
    *,
    headless: bool | None = None,
    notify_telegram: bool = True,
) -> List[TicketOption]:
    """Execute the search workflow for each configured route."""

    all_matches: List[TicketOption] = []
    for route in settings.iter_routes():
        tickets = await search_tickets(settings, route=route, headless=headless)
        filtered = filter_tickets(tickets, settings, route=route)
        if filtered:
            LOGGER.info(
                "Found %d matching tickets for %s ? %s",
                len(filtered),
                route.origin,
                route.destination,
            )
            print(format_ticket_table(filtered))
            if notify_telegram:
                if settings.telegram_bot_token and settings.telegram_chat_id:
                    LOGGER.info("Attempting Telegram notification for %d tickets", len(filtered))
                    try:
                        send_telegram_alert(
                            token=settings.telegram_bot_token,
                            chat_id=settings.telegram_chat_id,
                            tickets=filtered,
                            base_url=settings.base_url,
                        )
                        LOGGER.info("Telegram notification finished for %d tickets", len(filtered))
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.exception("Telegram notification failed: %s", exc)
                else:
                    LOGGER.warning(
                        "Telegram bot token or chat_id is not configured. Skipping Telegram notification."
                    )
            await _dispatch_email_notifications(filtered, settings)
            all_matches.extend(filtered)
            if settings.auto_book_enabled:
                try:
                    await maybe_book_ticket(filtered[0], settings, headless=headless)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error("Auto-book attempt failed: %s", exc)
        else:
            LOGGER.info("No matches for %s ? %s", route.origin, route.destination)
    return all_matches


async def watch_loop(settings: Settings, *, headless: bool | None = None) -> None:
    """Continuously poll according to POLLING_INTERVAL_MINUTES."""

    sleep_seconds = max(1, settings.polling_interval_minutes * 60)
    while True:
        started = datetime.now()
        matched_tickets: List[TicketOption] = []
        try:
            matched_tickets = await run_search_once(settings, headless=headless, notify_telegram=False)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Search cycle crashed: %s", exc)
        finally:
            elapsed = (datetime.now() - started).total_seconds()
            LOGGER.info("Cycle took %.1fs", elapsed)
        if matched_tickets:
            if settings.telegram_bot_token and settings.telegram_chat_id:
                LOGGER.info("Attempting Telegram notification for %d tickets (watch mode)", len(matched_tickets))
                try:
                    send_telegram_alert(
                        token=settings.telegram_bot_token,
                        chat_id=settings.telegram_chat_id,
                        tickets=matched_tickets,
                        base_url=settings.base_url,
                    )
                    LOGGER.info("Telegram notification finished for %d tickets (watch mode)", len(matched_tickets))
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("Telegram notification failed (watch mode): %s", exc)
            else:
                LOGGER.warning(
                    "Telegram bot token or chat_id is not configured. Skipping Telegram notification."
                )
        await asyncio.sleep(sleep_seconds)


async def _dispatch_email_notifications(tickets: List[TicketOption], settings: Settings) -> None:
    if not (settings.email_sender and settings.email_recipient and settings.smtp_host):
        return
    try:
        await asyncio.to_thread(email_notifier.send_email_notification, tickets, settings)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Email notifier error: %s", exc)
