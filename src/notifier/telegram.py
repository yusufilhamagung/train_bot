from __future__ import annotations

import logging
from typing import Sequence

import requests

from ..models.ticket import TicketOption

LOGGER = logging.getLogger(__name__)
API_BASE = "https://api.telegram.org"


def send_telegram_alert(
    token: str,
    chat_id: str,
    tickets: Sequence[TicketOption],
    *,
    base_url: str,
) -> None:
    """Send a Telegram message summarizing the matching tickets."""

    if not tickets:
        return

    lines = ["?? Train Ticket Alert", ""]
    for ticket in tickets:
        lines.append(
            "{train} {origin}->{destination} {depart} | {price}{currency} | seats {seats}".format(
                train=ticket.short_label(),
                origin=ticket.origin,
                destination=ticket.destination,
                depart=ticket.departure_datetime.strftime("%Y-%m-%d %H:%M"),
                price=ticket.price,
                currency=ticket.currency,
                seats=ticket.seats_available,
            )
        )
    lines.append("")
    lines.append(f"Book manually at {base_url}")

    url = f"{API_BASE}/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": "\n".join(lines), "disable_web_page_preview": True}
    response = requests.post(url, json=payload, timeout=10)
    if response.status_code >= 400:
        LOGGER.error("Telegram notification failed: %s | %s", response.status_code, response.text)
    else:
        LOGGER.info("Telegram notification sent")
