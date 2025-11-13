from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
import json
import os
from pathlib import Path
from typing import Any, Iterable, List

from dotenv import load_dotenv

load_dotenv()

_TIME_FMT = "%H:%M"
_DATE_FMT = "%Y-%m-%d"


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_int(value: str | None, default: int | None = None) -> int | None:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, _DATE_FMT).date()


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return datetime.strptime(value, _TIME_FMT).time()


def _resolve_path(path_str: str | None) -> Path | None:
    if not path_str:
        return None
    candidate = Path(path_str).expanduser().resolve()
    return candidate if candidate.exists() else None


@dataclass(slots=True)
class RoutePreference:
    """Represents a single origin/destination/date search configuration."""

    origin: str
    destination: str
    departure_date: date
    preferred_departure_time_start: time | None = None
    preferred_departure_time_end: time | None = None
    max_price: int | None = None
    min_seats: int | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RoutePreference":
        return cls(
            origin=payload["origin"],
            destination=payload["destination"],
            departure_date=_parse_date(payload["departure_date"]),
            preferred_departure_time_start=_parse_time(payload.get("preferred_departure_time_start")),
            preferred_departure_time_end=_parse_time(payload.get("preferred_departure_time_end")),
            max_price=_parse_int(str(payload.get("max_price")) if payload.get("max_price") is not None else None),
            min_seats=_parse_int(str(payload.get("min_seats")) if payload.get("min_seats") is not None else None),
        )


@dataclass(slots=True)
class PassengerProfile:
    """Passenger data used during the optional booking flow."""

    full_name: str
    national_id: str
    birth_date: date

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PassengerProfile":
        return cls(
            full_name=payload["full_name"],
            national_id=payload["national_id"],
            birth_date=_parse_date(payload["birth_date"]),
        )


@dataclass(slots=True)
class Settings:
    """Aggregated runtime configuration."""

    base_url: str
    origin_station: str
    destination_station: str
    departure_date: date
    preferred_departure_time_start: time | None
    preferred_departure_time_end: time | None
    passenger_count: int
    max_price: int | None
    min_seats_available: int
    polling_interval_minutes: int
    auto_book_enabled: bool
    headless: bool
    currency: str
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    routes_file: Path | None = None
    route_preferences: List[RoutePreference] = field(default_factory=list)
    passengers_file: Path | None = None
    passenger_profiles: List[PassengerProfile] = field(default_factory=list)
    email_sender: str | None = None
    email_recipient: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None

    def to_route_preference(self) -> RoutePreference:
        return RoutePreference(
            origin=self.origin_station,
            destination=self.destination_station,
            departure_date=self.departure_date,
            preferred_departure_time_start=self.preferred_departure_time_start,
            preferred_departure_time_end=self.preferred_departure_time_end,
            max_price=self.max_price,
            min_seats=self.min_seats_available,
        )

    def iter_routes(self) -> Iterable[RoutePreference]:
        return self.route_preferences or [self.to_route_preference()]


def _load_route_preferences(path: Path | None) -> List[RoutePreference]:
    if not path:
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Routes JSON must be a list of route objects")
    return [RoutePreference.from_dict(item) for item in payload]


def _load_passenger_profiles(path: Path | None) -> List[PassengerProfile]:
    if not path:
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Passengers JSON must be a list of passenger objects")
    return [PassengerProfile.from_dict(item) for item in payload]


def load_settings(routes_file: str | Path | None = None) -> Settings:
    """Load configuration from environment variables and optional JSON files."""

    base_url = os.getenv("BASE_URL", "https://kai.id") or "https://kai.id"

    origin = os.getenv("ORIGIN_STATION")
    destination = os.getenv("DESTINATION_STATION")
    departure_date_raw = os.getenv("DEPARTURE_DATE")
    if not all([origin, destination, departure_date_raw]):
        raise ValueError("ORIGIN_STATION, DESTINATION_STATION, and DEPARTURE_DATE are required")

    passenger_count = int(os.getenv("PASSENGER_COUNT", "1"))
    polling_interval = int(os.getenv("POLLING_INTERVAL_MINUTES", "5"))
    auto_book_enabled = _parse_bool(os.getenv("AUTO_BOOK_ENABLED"))
    headless = _parse_bool(os.getenv("HEADLESS"), default=True)
    max_price = _parse_int(os.getenv("MAX_PRICE"))
    min_seats = _parse_int(os.getenv("MIN_SEATS_AVAILABLE"), default=passenger_count) or passenger_count

    preferred_start = _parse_time(os.getenv("PREFERRED_DEPARTURE_TIME_START"))
    preferred_end = _parse_time(os.getenv("PREFERRED_DEPARTURE_TIME_END"))
    currency = os.getenv("CURRENCY", "IDR")

    resolved_routes_path = (
        Path(routes_file).expanduser().resolve() if routes_file else _resolve_path(os.getenv("ROUTES_FILE"))
    )
    resolved_passengers_path = _resolve_path(os.getenv("PASSENGERS_FILE"))

    route_preferences = _load_route_preferences(resolved_routes_path)
    passenger_profiles = _load_passenger_profiles(resolved_passengers_path)

    return Settings(
        base_url=base_url,
        origin_station=origin,
        destination_station=destination,
        departure_date=_parse_date(departure_date_raw),
        preferred_departure_time_start=preferred_start,
        preferred_departure_time_end=preferred_end,
        passenger_count=passenger_count,
        max_price=max_price,
        min_seats_available=min_seats,
        polling_interval_minutes=polling_interval,
        auto_book_enabled=auto_book_enabled,
        headless=headless,
        currency=currency,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        routes_file=resolved_routes_path,
        route_preferences=route_preferences,
        passengers_file=resolved_passengers_path,
        passenger_profiles=passenger_profiles,
        email_sender=os.getenv("EMAIL_SENDER"),
        email_recipient=os.getenv("EMAIL_RECIPIENT"),
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=_parse_int(os.getenv("SMTP_PORT")),
        smtp_username=os.getenv("SMTP_USERNAME"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
    )
