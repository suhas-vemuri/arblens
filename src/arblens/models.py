from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


@dataclass(frozen=True, slots=True)
class QuoteIssue:
    row_index: int
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class Violation:
    violation_type: str
    option_type: str
    expiration: str
    strikes: tuple[float, ...]
    magnitude: float
    price_basis: str
    details: str
    detected_at: datetime | None = None
