from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(slots=True)
class TicketOption:
    """Normalized representation of a ticket row scraped from the site."""

    train_name: str
    train_number: str | None
    class_name: str
    origin: str
    destination: str
    departure_datetime: datetime
    arrival_datetime: datetime
    price: int
    currency: str
    seats_available: int
    raw_data: Dict[str, Any] | None = field(default=None)
    departure_label: Optional[str] = None

    def short_label(self) -> str:
        return f"{self.train_name} ({self.train_number or 'N/A'})"

    def summary_line(self) -> str:
        depart = self.departure_datetime.strftime("%Y-%m-%d %H:%M")
        arrive = self.arrival_datetime.strftime("%Y-%m-%d %H:%M")
        return (
            f"{self.short_label()} | {self.class_name} | "
            f"{self.origin}->{self.destination} | {depart} ? {arrive} | "
            f"{self.price} {self.currency} | seats: {self.seats_available}"
        )


@dataclass(slots=True)
class TrainResult:
    """Rich representation of a train row regardless of availability."""

    name: str
    number: Optional[str]
    departure_station: str
    departure_time: str
    arrival_station: str
    arrival_time: str
    duration: Optional[str] = None
    travel_class: Optional[str] = None
    subclass: Optional[str] = None
    price: Optional[int] = None
    currency: Optional[str] = None
    status: str = "Status tidak diketahui"
    is_available: bool = False
    seats_remaining: Optional[int] = None
    departure_label: Optional[str] = None


@dataclass(slots=True)
class SearchSummary:
    """Snapshot of the active route/date as rendered on the site."""

    origin_label: str
    destination_label: str
    date_label: str
