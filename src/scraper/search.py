from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Sequence

from playwright.async_api import ElementHandle, TimeoutError as PlaywrightTimeout

from ..config.settings import RoutePreference, Settings
from ..models.ticket import TicketOption
from .browser import create_page, close_browser

LOGGER = logging.getLogger(__name__)

ORIGIN_FIELD_SELECTOR = 'div._stationInfoTop_1nmpp_130'
DESTINATION_FIELD_SELECTOR = (
    'div._stationInfoBottom_1nmpp_138, '
    'div._stationInfoBottom_1nmpp_138:has-text("YOGYAKARTA"), '
    'div:has-text("LEMPUYANGAN (LPN)")'
)

STATION_INPUT_SELECTOR = 'input[placeholder="Cari Stasiun"]'
ORIGIN_INPUT_SELECTOR = STATION_INPUT_SELECTOR
DESTINATION_INPUT_SELECTOR = STATION_INPUT_SELECTOR
STATION_SELECT_DELAY_MS = 800
STATION_SUGGESTION_SELECTOR_TEMPLATE = 'span._stationLabelName_xg1at_50.sc-ion-label-md:has-text("{name}")'
DETAIL_CONTENT_SELECTOR = 'div._detailContent_1nmpp_206'
DATE_FIELD_SELECTOR = f'{DETAIL_CONTENT_SELECTOR} >> nth=0'
PASSENGER_FIELD_SELECTOR = f'{DETAIL_CONTENT_SELECTOR} >> nth=1'
PASSENGER_COUNTER_CONTAINER_SELECTOR = 'div._counterItem_ho7zr_20'
PASSENGER_COUNTER_LABEL_SELECTOR = f'{PASSENGER_COUNTER_CONTAINER_SELECTOR} p._counterLabel_ho7zr_27'
PASSENGER_DECREMENT_BUTTON_SELECTOR = (
    f'{PASSENGER_COUNTER_CONTAINER_SELECTOR} div._btnIncrementDecrement_ho7zr_34 >> nth=0'
)
PASSENGER_INCREMENT_BUTTON_SELECTOR = (
    f'{PASSENGER_COUNTER_CONTAINER_SELECTOR} div._btnIncrementDecrement_ho7zr_34 >> nth=1'
)
SEARCH_BUTTON_SELECTOR = "div._cardButton_1nmpp_226"
RESULT_ROW_SELECTOR = "div._mainContent_1w15y_43"
TRAIN_NAME_SELECTOR = "p._trainName__1w15y_64"
# TRAIN_NUMBER_SELECTOR = "TODO: fill selector for train number"
# CLASS_NAME_SELECTOR = "TODO: fill selector for class/cabin"
# DEPARTURE_SELECTOR = "TODO: fill selector for departure datetime"
# ARRIVAL_SELECTOR = "TODO: fill selector for arrival datetime"
# PRICE_SELECTOR = "TODO: fill selector for price"
# SEATS_SELECTOR = "TODO: fill selector for seat availability"
# BOOK_BUTTON_SELECTOR = "TODO: fill selector for book/reserve button"


async def search_tickets(
    config: Settings,
    route: RoutePreference | None = None,
    *,
    headless: bool | None = None,
) -> List[TicketOption]:
    """Use Playwright to perform a ticket search."""

    active_route = route or config.to_route_preference()
    resolved_headless = config.headless if headless is None else headless
    playwright, browser, context, page = await create_page(headless=resolved_headless)
    tickets: List[TicketOption] = []

    try:
        await page.goto(config.base_url, wait_until="domcontentloaded")
        await page.click(ORIGIN_FIELD_SELECTOR)
        await page.wait_for_selector(ORIGIN_INPUT_SELECTOR, timeout=30_000)
        await page.fill(ORIGIN_INPUT_SELECTOR, active_route.origin)
        await page.wait_for_timeout(STATION_SELECT_DELAY_MS)
        await page.click(
            STATION_SUGGESTION_SELECTOR_TEMPLATE.format(name=active_route.origin)
        )
        await page.wait_for_timeout(1_000)

        await page.locator(DESTINATION_FIELD_SELECTOR).click(timeout=30_000, force=True)
        await page.wait_for_selector(DESTINATION_INPUT_SELECTOR, timeout=30_000)
        await page.fill(DESTINATION_INPUT_SELECTOR, active_route.destination)
        await page.wait_for_timeout(STATION_SELECT_DELAY_MS)
        await page.click(
            STATION_SUGGESTION_SELECTOR_TEMPLATE.format(name=active_route.destination)
        )

        try:
            await page.locator(DATE_FIELD_SELECTOR).click()
        except Exception:  # noqa: BLE001
            pass

        try:
            await page.locator(PASSENGER_FIELD_SELECTOR).click()
            target_count = config.passenger_count
            if target_count and target_count > 0:
                counter_locator = page.locator(PASSENGER_COUNTER_LABEL_SELECTOR)
                try:
                    await counter_locator.wait_for(timeout=30_000)
                    current_label = (await counter_locator.inner_text()).strip()
                    try:
                        current_count = int(current_label or "0")
                    except ValueError:
                        current_count = 0
                    increment_button = page.locator(PASSENGER_INCREMENT_BUTTON_SELECTOR)
                    decrement_button = page.locator(PASSENGER_DECREMENT_BUTTON_SELECTOR)
                    LOGGER.debug("Passenger counter current=%s target=%s", current_count, target_count)
                    if target_count > current_count:
                        for _ in range(target_count - current_count):
                            await increment_button.click()
                            await page.wait_for_timeout(150)
                    elif target_count < current_count:
                        for _ in range(current_count - target_count):
                            await decrement_button.click()
                            await page.wait_for_timeout(150)
                    LOGGER.debug("Passenger counter adjusted to %s", target_count)
                except PlaywrightTimeout:
                    LOGGER.warning("Passenger counter label did not appear in time")
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("Failed to adjust passenger count: %s", exc)
            try:
                await page.click('button:has-text("Konfirmasi")')
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass
        await page.click(SEARCH_BUTTON_SELECTOR)
        await page.wait_for_selector(RESULT_ROW_SELECTOR, timeout=30_000)
        rows = await page.query_selector_all(RESULT_ROW_SELECTOR)
        for row in rows:
            try:
                ticket = await _parse_row(row, config)
                tickets.append(ticket)
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Failed to parse row: %s", exc)
    except PlaywrightTimeout as exc:
        LOGGER.warning("Search timed out: %s", exc)
    finally:
        await close_browser(playwright, browser, context)

    LOGGER.info(
        "Scraped %d tickets for %s ? %s on %s",
        len(tickets),
        active_route.origin,
        active_route.destination,
        active_route.departure_date,
    )
    return tickets


async def _parse_row(element: ElementHandle, config: Settings) -> TicketOption:
    train_name = await _maybe_text(element, TRAIN_NAME_SELECTOR, default="Unknown Train")
    train_number = await _maybe_text(element, TRAIN_NUMBER_SELECTOR, default=None)
    class_name = await _maybe_text(element, CLASS_NAME_SELECTOR, default="Unknown Class")
    departure_raw = await _maybe_text(element, DEPARTURE_SELECTOR, default="1970-01-01 00:00") or ""
    arrival_raw = await _maybe_text(element, ARRIVAL_SELECTOR, default="1970-01-01 00:00") or ""
    price_raw = await _maybe_text(element, PRICE_SELECTOR, default="0") or "0"
    seats_raw = await _maybe_text(element, SEATS_SELECTOR, default=str(config.min_seats_available)) or str(
        config.min_seats_available
    )

    departure_dt = _parse_datetime_fallback(departure_raw)
    arrival_dt = _parse_datetime_fallback(arrival_raw)
    price = _parse_price(price_raw)
    seats = _parse_int(seats_raw, default=config.min_seats_available)

    return TicketOption(
        train_name=train_name,
        train_number=train_number,
        class_name=class_name,
        origin=config.origin_station,
        destination=config.destination_station,
        departure_datetime=departure_dt,
        arrival_datetime=arrival_dt,
        price=price,
        currency=config.currency,
        seats_available=seats,
        raw_data={
            "price_raw": price_raw,
            "seats_raw": seats_raw,
        },
    )


async def _maybe_text(element: ElementHandle, selector: str, *, default: str | None) -> str | None:
    if "TODO" in selector:
        return default
    handle = await element.query_selector(selector)
    if not handle:
        return default
    text = await handle.inner_text()
    text = text.strip()
    return text or default


def _parse_datetime_fallback(raw: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%H:%M"):
        try:
            parsed = datetime.strptime(raw.strip(), fmt)
            if fmt == "%H:%M":
                today = datetime.utcnow()
                parsed = parsed.replace(year=today.year, month=today.month, day=today.day)
            return parsed
        except ValueError:
            continue
    return datetime.utcnow()


def _parse_price(raw: str) -> int:
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else 0


def _parse_int(raw: str, *, default: int) -> int:
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else default


def filter_tickets(
    tickets: Sequence[TicketOption],
    config: Settings,
    route: RoutePreference | None = None,
) -> List[TicketOption]:
    """Filter tickets using config and route preferences."""

    active_route = route or config.to_route_preference()
    max_price = active_route.max_price if active_route.max_price is not None else config.max_price
    min_seats = active_route.min_seats if active_route.min_seats is not None else config.min_seats_available
    start_time = active_route.preferred_departure_time_start or config.preferred_departure_time_start
    end_time = active_route.preferred_departure_time_end or config.preferred_departure_time_end

    filtered: List[TicketOption] = []
    for ticket in tickets:
        if ticket.departure_datetime.date() != active_route.departure_date:
            continue
        dep_time = ticket.departure_datetime.time()
        if start_time and dep_time < start_time:
            continue
        if end_time and dep_time > end_time:
            continue
        if max_price is not None and ticket.price > max_price:
            continue
        if ticket.seats_available < max(min_seats, config.passenger_count):
            continue
        filtered.append(ticket)
    return filtered


def format_ticket_table(tickets: Sequence[TicketOption]) -> str:
    """Return a simple ASCII table summarizing tickets."""

    if not tickets:
        return "No tickets to display."

    headers = ["Train", "Class", "Depart", "Arrive", "Price", "Seats"]
    rows = [
        [
            ticket.short_label(),
            ticket.class_name,
            ticket.departure_datetime.strftime("%Y-%m-%d %H:%M"),
            ticket.arrival_datetime.strftime("%Y-%m-%d %H:%M"),
            f"{ticket.price} {ticket.currency}",
            str(ticket.seats_available),
        ]
        for ticket in tickets
    ]

    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    header_line = " | ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers))
    divider = "-+-".join("-" * width for width in widths)
    data_lines = [" | ".join(row[idx].ljust(widths[idx]) for idx in range(len(headers))) for row in rows]
    return "\n".join([header_line, divider, *data_lines])
