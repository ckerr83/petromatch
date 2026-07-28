from __future__ import annotations

import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime


def normalize_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def normalize_text(value: str | None) -> str:
    return normalize_whitespace(value or "") or ""


def tokenize(value: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+", (value or "").lower())


def parse_date_safe(value: str | None) -> date | None:
    if not value:
        return None
    for parser in (datetime.fromisoformat, parsedate_to_datetime):
        try:
            parsed = parser(value)
            return parsed.date()
        except (TypeError, ValueError, IndexError):
            continue
    return None

