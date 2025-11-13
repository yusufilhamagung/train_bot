from __future__ import annotations

import logging
from typing import Iterable, List, Sequence

import requests

from ..models.ticket import SearchSummary, TicketOption, TrainResult

LOGGER = logging.getLogger(__name__)
API_BASE = "https://api.telegram.org"
TELEGRAM_MESSAGE_LIMIT = 4000
SECTION_DIVIDER = "────────────────────"


def send_telegram_alert(
    token: str,
    chat_id: str,
    tickets: Sequence[TicketOption],
    *,
    base_url: str,
) -> None:
    """Send a Telegram message summarizing matching tickets (available only)."""

    if not tickets:
        return

    lines: list[str] = []
    lines.append("🚆 TRAIN TICKET ALERT")
    lines.append("")

    for idx, ticket in enumerate(tickets, start=1):
        price_str = f"{ticket.price:,}".replace(",", ".")
        depart_str = ticket.departure_label or ticket.departure_datetime.strftime("%Y-%m-%d %H:%M")

        lines.append(f"#{idx} {ticket.short_label()}")
        lines.append(f"   {ticket.origin} -> {ticket.destination}")
        lines.append(f"   Depart : {depart_str}")
        lines.append(f"   Price  : Rp {price_str} ({ticket.currency})")
        lines.append(f"   Seats  : {ticket.seats_available}")
        lines.append("")
        lines.append(SECTION_DIVIDER)
        lines.append("")

    lines.append(SECTION_DIVIDER)
    lines.append(f"Book manually at {base_url}")

    _post_message(token, chat_id, "\n".join(lines))


def send_train_results_summary(
    *,
    token: str,
    chat_id: str,
    summary: SearchSummary,
    trains: Sequence[TrainResult],
) -> None:
    """Send every scraped train row (available or not) to Telegram."""

    message = format_train_results_message(summary, trains)
    for chunk in split_message_for_telegram(message):
        if chunk.strip():
            _post_message(token, chat_id, chunk)


def format_train_results_message(
    summary: SearchSummary,
    trains: Iterable[TrainResult],
) -> str:
    train_rows = list(trains)
    total_trains = len(train_rows)
    available_trains = sum(1 for train in train_rows if train.is_available)
    unavailable_trains = total_trains - available_trains
    origin = summary.origin_label or "-"
    destination = summary.destination_label or "-"
    date_label = summary.date_label or "-"

    lines = [
        "🚆 Train Ticket Alert",
        "",
        f"📍 Rute   : {origin} -> {destination}",
        f"📅 Tanggal: {date_label}",
        "",
    ]

    if not train_rows:
        lines.append("Tidak ada kereta ditemukan.")
        return "\n".join(lines)

    lines.extend(
        [
            f"Total kereta   : {total_trains}",
            f"Tersedia       : {available_trains}",
            f"Tidak tersedia : {unavailable_trains}",
            SECTION_DIVIDER,
        ]
    )

    for idx, train in enumerate(train_rows, start=1):
        lines.extend(_format_train_block(train, idx))
        lines.append(SECTION_DIVIDER)

    return "\n".join(lines).strip()


def split_message_for_telegram(text: str, max_length: int = TELEGRAM_MESSAGE_LIMIT) -> List[str]:
    """Split large telegram payloads into safe chunks."""

    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    current_lines: List[str] = []
    current_len = 0

    def flush_current() -> None:
        nonlocal current_lines, current_len
        if current_lines:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_len = 0

    for line in text.splitlines():
        line_len = len(line)
        if line_len > max_length:
            flush_current()
            for start in range(0, line_len, max_length):
                chunks.append(line[start : start + max_length])
            continue

        addition = line_len if not current_lines else line_len + 1
        if current_len + addition > max_length:
            flush_current()
        current_lines.append(line)
        current_len += addition

    flush_current()
    return chunks or [""]


def _format_train_block(train: TrainResult, index: int) -> List[str]:
    block: List[str] = []
    status_icon = "✅" if train.is_available else "❌"
    status_text = "Tersedia" if train.is_available else "Tidak tersedia"
    name_line = f"{train.name} ({train.number})" if train.number else train.name
    route_line = f"{train.departure_station} {train.departure_time} -> {train.arrival_station} {train.arrival_time}"
    duration_line = train.duration or "-"
    class_label = train.travel_class or "-"
    if train.subclass:
        class_label = f"{class_label} ({train.subclass})" if class_label != "-" else train.subclass
    price_line = _format_price(train.price)

    block.append(f"#{index} {status_icon} {status_text}")
    block.append(name_line)
    block.append(route_line)
    block.append(f"Durasi : {duration_line}")
    block.append(f"Kelas  : {class_label}")
    block.append(f"Harga  : {price_line}")
    if not train.is_available:
        block.append(f"Status : {train.status or 'Tidak tersedia'}")
    return block


def _format_price(value: int | None) -> str:
    if value is None:
        return "-"
    return f"Rp {value:,}".replace(",", ".")


def _post_message(token: str, chat_id: str, text: str) -> None:
    url = f"{API_BASE}/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    response = requests.post(url, json=payload, timeout=10)
    if response.status_code >= 400:
        LOGGER.error("Telegram notification failed: %s | %s", response.status_code, response.text)
    else:
        LOGGER.info("Telegram notification sent")
