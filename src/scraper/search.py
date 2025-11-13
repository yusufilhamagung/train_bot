from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Sequence

from playwright.async_api import ElementHandle, Locator, Page, TimeoutError as PlaywrightTimeout

from ..config.settings import RoutePreference, Settings
from ..models.ticket import SearchSummary, TicketOption, TrainResult
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
PASSENGER_FIELD_TRIGGER_SELECTOR = 'div._detailItem_1nmpp_195:has(p._detailTitle_1nmpp_200:has-text("Penumpang"))'
PASSENGER_MODAL_SELECTOR = 'div._counterGroup_ho7zr_3'
PASSENGER_SECTION_SELECTOR = 'div._counterSection_ho7zr_8'
PASSENGER_ADULT_SECTION_SELECTOR = f'{PASSENGER_SECTION_SELECTOR}:has-text("DEWASA")'
PASSENGER_COUNT_VALUE_SELECTOR = 'p._counterLabel_ho7zr_27'
PASSENGER_ADJUST_BUTTON_SELECTOR = 'div._btnIncremenDecrement_ho7zr_34'
PASSENGER_CONFIRM_BUTTON_SELECTOR = 'div._btnConfirmation_ho7zr_49'
SEARCH_BUTTON_SELECTOR = "div._cardButton_1nmpp_226"
RESULT_ROW_SELECTOR = "ion-card._scheduleCard_1w15y_47"
SEARCH_HEADER_ROUTE_SELECTOR = "p._headerScheduleRoute_1vmjn_26"
SEARCH_HEADER_INFO_SELECTOR = "p._headerScheduleTime_1vmjn_32"
DATE_INPUT_FALLBACK_SELECTOR = f"{DATE_FIELD_SELECTOR} input"
TRAIN_NAME_SELECTOR = "p._trainName_1w15y_64"
TRAIN_CLASS_SELECTOR = "p._trainClass_1w15y_70"
TIME_RANGE_SELECTOR = "p._time_1w15y_82"
DURATION_SELECTOR = "span._duration_1w15y_88"
PRICE_SELECTOR = "p._price_1w15y_94"
AVAILABILITY_SELECTOR = "p._availability_1w15y_100"


@dataclass(slots=True)
class TrainSearchResults:
    """Container holding every scraped train row and derived ticket options."""

    summary: SearchSummary
    trains: List[TrainResult]
    tickets: List[TicketOption]


async def search_tickets(
    config: Settings,
    route: RoutePreference | None = None,
    *,
    headless: bool | None = None,
) -> List[TicketOption]:
    """Legacy helper that returns only available tickets."""

    results = await search_train_results(config, route=route, headless=headless)
    return results.tickets


async def search_train_results(
    config: Settings,
    route: RoutePreference | None = None,
    *,
    headless: bool | None = None,
) -> TrainSearchResults:
    """Use Playwright to perform a ticket search and return every row."""

    return await _execute_search(config, route=route, headless=headless)


async def _execute_search(
    config: Settings,
    route: RoutePreference | None,
    *,
    headless: bool | None,
) -> TrainSearchResults:
    active_route = route or config.to_route_preference()
    resolved_headless = config.headless if headless is None else headless
    playwright, browser, context, page = await create_page(headless=resolved_headless)
    summary: SearchSummary | None = None
    trains: List[TrainResult] = []
    tickets: List[TicketOption] = []

    try:
        await page.goto(config.base_url, wait_until="domcontentloaded")
        await page.click(ORIGIN_FIELD_SELECTOR)
        await page.wait_for_selector(ORIGIN_INPUT_SELECTOR, timeout=30_000)
        await page.fill(ORIGIN_INPUT_SELECTOR, active_route.origin)
        await page.wait_for_timeout(STATION_SELECT_DELAY_MS)
        await page.click(STATION_SUGGESTION_SELECTOR_TEMPLATE.format(name=active_route.origin))
        await page.wait_for_timeout(1_000)

        await page.locator(DESTINATION_FIELD_SELECTOR).click(timeout=30_000, force=True)
        await page.wait_for_selector(DESTINATION_INPUT_SELECTOR, timeout=30_000)
        await page.fill(DESTINATION_INPUT_SELECTOR, active_route.destination)
        await page.wait_for_timeout(STATION_SELECT_DELAY_MS)
        await page.click(STATION_SUGGESTION_SELECTOR_TEMPLATE.format(name=active_route.destination))

        try:
            await page.locator(DATE_FIELD_SELECTOR).click()
        except Exception:  # noqa: BLE001
            pass

        await _set_adult_passenger_count(page, config.passenger_count)
        await page.click(SEARCH_BUTTON_SELECTOR)
        await page.wait_for_selector(RESULT_ROW_SELECTOR, timeout=30_000)
        summary = await _extract_search_summary(page, active_route)
        rows = await page.query_selector_all(RESULT_ROW_SELECTOR)
        for row in rows:
            try:
                train = await _parse_train_row(row, config, active_route)
                trains.append(train)
                ticket = _train_result_to_ticket(train, config, active_route)
                if ticket:
                    tickets.append(ticket)
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Failed to parse row: %s", exc)
    except PlaywrightTimeout as exc:
        LOGGER.warning("Search timed out: %s", exc)
    finally:
        await close_browser(playwright, browser, context)

    if summary is None:
        summary = _fallback_summary(active_route)

    LOGGER.info(
        "Scraped %d trains (%d available) for %s ? %s on %s",
        len(trains),
        len(tickets),
        summary.origin_label,
        summary.destination_label,
        summary.date_label,
    )
    return TrainSearchResults(summary=summary, trains=trains, tickets=tickets)


async def _parse_train_row(element: ElementHandle, config: Settings, route: RoutePreference) -> TrainResult:
    train_name = await _maybe_text(element, TRAIN_NAME_SELECTOR, default="Unknown Train") or "Unknown Train"
    class_label = await _maybe_text(element, TRAIN_CLASS_SELECTOR, default=None)
    travel_class, subclass = _split_class_label(class_label)
    time_range = await _maybe_text(element, TIME_RANGE_SELECTOR, default="") or ""
    time_label = _clean_label(time_range) or ""
    departure_time, arrival_time = _split_time_range(time_range)
    duration_raw = await _maybe_text(element, DURATION_SELECTOR, default=None)
    duration = _normalize_duration(duration_raw)
    price_raw = await _maybe_text(element, PRICE_SELECTOR, default=None)
    price = _parse_price(price_raw or "") if price_raw else None
    availability_raw = await _maybe_text(element, AVAILABILITY_SELECTOR, default="Status tidak diketahui") or ""
    availability_clean = availability_raw.strip() or "Status tidak diketahui"
    seats_remaining = _extract_first_int(availability_clean)
    is_available = _is_status_available(availability_clean)

    return TrainResult(
        name=train_name.strip(),
        number=None,
        departure_station=route.origin,
        departure_time=departure_time or "--:--",
        arrival_station=route.destination,
        arrival_time=arrival_time or "--:--",
        duration=duration,
        travel_class=travel_class,
        subclass=subclass,
        price=price,
        currency=config.currency,
        status=availability_clean,
        is_available=is_available,
        seats_remaining=seats_remaining,
        departure_label=time_label,
    )


def _train_result_to_ticket(
    train: TrainResult,
    config: Settings,
    route: RoutePreference,
) -> TicketOption | None:
    if not train.is_available:
        return None

    departure_dt = _combine_time_with_date(route.departure_date, train.departure_time)
    arrival_dt = _combine_time_with_date(route.departure_date, train.arrival_time)
    if arrival_dt < departure_dt:
        arrival_dt += timedelta(days=1)

    price = train.price if train.price is not None else 0
    seats = train.seats_remaining if train.seats_remaining is not None else config.min_seats_available
    class_label = train.travel_class or "Unknown Class"
    if train.subclass:
        class_label = f"{class_label} - {train.subclass}"

    return TicketOption(
        train_name=train.name,
        train_number=train.number,
        class_name=class_label,
        origin=train.departure_station,
        destination=train.arrival_station,
        departure_datetime=departure_dt,
        arrival_datetime=arrival_dt,
        price=price,
        currency=train.currency or config.currency,
        seats_available=seats,
        raw_data={
            "status": train.status,
            "duration": train.duration,
        },
        departure_label=train.departure_label,
    )


async def _extract_search_summary(page: Page, route: RoutePreference) -> SearchSummary:
    origin_label = route.origin
    destination_label = route.destination
    date_label = route.departure_date.strftime("%d %b %Y")

    try:
        header_route = page.locator(SEARCH_HEADER_ROUTE_SELECTOR).first
        if await header_route.count():
            header_text = _clean_label(await header_route.inner_text())
            parsed_origin, parsed_destination = _split_route_text(header_text)
            origin_label = parsed_origin or origin_label
            destination_label = parsed_destination or destination_label
        else:
            raise PlaywrightTimeout("Header route missing")
    except Exception:  # noqa: BLE001
        extracted_origin = await _extract_station_label(page, ORIGIN_FIELD_SELECTOR)
        extracted_destination = await _extract_station_label(page, DESTINATION_FIELD_SELECTOR)
        if extracted_origin:
            origin_label = extracted_origin
        if extracted_destination:
            destination_label = extracted_destination

    try:
        header_info = page.locator(SEARCH_HEADER_INFO_SELECTOR).first
        if await header_info.count():
            info_text = _clean_label(await header_info.inner_text())
            candidate = info_text.split("|", 1)[0].strip() if info_text else ""
            date_label = candidate or date_label
        else:
            raise PlaywrightTimeout("Header date missing")
    except Exception:  # noqa: BLE001
        date_from_input = await _extract_date_from_input(page)
        if date_from_input:
            date_label = date_from_input

    return SearchSummary(
        origin_label=origin_label,
        destination_label=destination_label,
        date_label=date_label,
    )


async def _extract_station_label(page: Page, selector: str) -> str | None:
    try:
        node = page.locator(selector).first
        if await node.count() == 0:
            return None
        text = await node.inner_text()
        return _clean_label(text)
    except Exception:  # noqa: BLE001
        return None


async def _extract_date_from_input(page: Page) -> str | None:
    try:
        input_locator = page.locator(DATE_INPUT_FALLBACK_SELECTOR).first
        if await input_locator.count() == 0:
            return None
        try:
            value = await input_locator.input_value()
        except Exception:  # noqa: BLE001
            value = await input_locator.get_attribute("value")
        return _clean_label(value)
    except Exception:  # noqa: BLE001
        return None


def _fallback_summary(route: RoutePreference) -> SearchSummary:
    return SearchSummary(
        origin_label=route.origin,
        destination_label=route.destination,
        date_label=route.departure_date.strftime("%d %b %Y"),
    )


def _split_route_text(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    for delimiter in (" -> ", " → ", " - ", " — "):
        if delimiter in raw:
            left, right = raw.split(delimiter, 1)
            return _clean_label(left), _clean_label(right)
    return _clean_label(raw), None


def _clean_label(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.split())


def _split_class_label(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    if "-" in raw:
        major, minor = raw.split("-", 1)
        return major.strip(), minor.strip()
    return raw.strip(), None


def _split_time_range(raw: str) -> tuple[str, str]:
    if not raw:
        return "", ""
    cleaned = raw.split("(")[0]
    parts = cleaned.split("-")
    depart = parts[0].strip() if parts else ""
    arrive = parts[1].strip() if len(parts) > 1 else ""
    return depart, arrive


def _normalize_duration(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.strip().strip("()")


def _extract_first_int(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else None


def _is_status_available(status: str) -> bool:
    lowered = status.lower()
    negative_markers = ("habis", "penuh", "waiting", "tutup", "tidak tersedia")
    if any(marker in lowered for marker in negative_markers):
        return False
    positive_markers = ("tersedia", "available", "ready", "open")
    return any(marker in lowered for marker in positive_markers)


def _combine_time_with_date(route_date: date, label: str) -> datetime:
    if not label:
        return datetime.combine(route_date, datetime.min.time())
    try:
        parsed_time = datetime.strptime(label.strip(), "%H:%M").time()
    except ValueError:
        return datetime.combine(route_date, datetime.min.time())
    return datetime.combine(route_date, parsed_time)


async def _maybe_text(element: ElementHandle, selector: str, *, default: str | None) -> str | None:
    if "TODO" in selector:
        return default
    handle = await element.query_selector(selector)
    if not handle:
        return default
    text = await handle.inner_text()
    text = text.strip()
    return text or default


def _parse_price(raw: str) -> int:
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else 0


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


async def _set_adult_passenger_count(page: Page, desired: int) -> None:
    """Ensure the adult passenger counter matches the desired configuration."""

    if desired <= 0:
        LOGGER.debug("Skipping passenger adjustment; desired count=%s", desired)
        return

    try:
        passenger_trigger = page.locator(PASSENGER_FIELD_TRIGGER_SELECTOR)
        await passenger_trigger.wait_for(timeout=30_000)
        await passenger_trigger.click()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Unable to open passenger selector: %s", exc)
        return

    passenger_modal = page.locator(PASSENGER_MODAL_SELECTOR)
    try:
        await passenger_modal.wait_for(timeout=30_000)
    except PlaywrightTimeout:
        LOGGER.warning("Passenger modal did not appear in time")
        return

    adult_section = passenger_modal.locator(PASSENGER_ADULT_SECTION_SELECTOR).first
    try:
        await adult_section.wait_for(timeout=30_000)
    except PlaywrightTimeout:
        LOGGER.warning("Adult passenger section is missing")
        return

    value_locator = adult_section.locator(PASSENGER_COUNT_VALUE_SELECTOR)
    if await value_locator.count() == 0:
        LOGGER.warning("Passenger counter value element not found")
        return

    adjust_buttons = adult_section.locator(PASSENGER_ADJUST_BUTTON_SELECTOR)
    if await adjust_buttons.count() < 2:
        LOGGER.warning("Passenger increment/decrement buttons not found")
        return

    count_locator = value_locator.first
    decrement_button = adjust_buttons.nth(0)
    increment_button = adjust_buttons.nth(1)

    current = await _read_passenger_value(count_locator)
    LOGGER.info("Setting adult passenger count from %s to %s", current, desired)

    while current < desired:
        await increment_button.click()
        await page.wait_for_timeout(200)
        current = await _read_passenger_value(count_locator)

    while current > desired:
        await decrement_button.click()
        await page.wait_for_timeout(200)
        current = await _read_passenger_value(count_locator)

    LOGGER.info("Passenger count confirmed at %s", current)

    confirm_button = passenger_modal.locator(PASSENGER_CONFIRM_BUTTON_SELECTOR).first
    if await confirm_button.count() > 0:
        await confirm_button.click()
    else:
        LOGGER.debug("Passenger confirmation button not found; modal may auto-close")


async def _read_passenger_value(locator: Locator) -> int:
    text = (await locator.inner_text()).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits or "0")
