from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


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
