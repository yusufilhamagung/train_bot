from datetime import datetime
import os
from types import SimpleNamespace

from src.notifier.telegram import send_telegram_alert

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

dummy_ticket = SimpleNamespace(
    short_label=lambda: "TEST123",
    origin="PSE",
    destination="LPN",
    departure_datetime=datetime(2025, 12, 24, 22, 0),
    price=350000,
    currency="IDR",
    seats_available=4,
)

tickets = [dummy_ticket]

send_telegram_alert(
    token=TOKEN,
    chat_id=CHAT_ID,
    tickets=tickets,
    base_url="https://example.com",
)
