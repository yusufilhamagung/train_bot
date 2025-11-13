from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Sequence

from ..config.settings import Settings
from ..models.ticket import TicketOption

LOGGER = logging.getLogger(__name__)


def send_email_notification(tickets: Sequence[TicketOption], settings: Settings) -> None:
    """Send a simple plain-text email summarizing ticket matches."""

    if not tickets:
        return
    if not (settings.email_sender and settings.email_recipient and settings.smtp_host):
        LOGGER.debug("Email notifier is not fully configured; skipping")
        return

    message = EmailMessage()
    message["Subject"] = "Train ticket alert"
    message["From"] = settings.email_sender
    message["To"] = settings.email_recipient
    body_lines = ["Matching tickets:"] + [ticket.summary_line() for ticket in tickets]
    message.set_content("\n".join(body_lines))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port or 587, timeout=10) as server:
            server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        LOGGER.info("Email notification sent")
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Email notification failed: %s", exc)
