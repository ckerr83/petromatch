from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class EmailParseContext:
    sender: str | None
    subject: str | None
    html_body: str | None
    plain_text_body: str | None


@dataclass(frozen=True)
class ParsedOpportunity:
    source: str
    job_title: str | None
    company: str | None
    location: str | None
    job_url: str | None
    posted_date: date | None
    raw_text: str
    external_id: str | None = None


class EmailJobParser(Protocol):
    source: str

    def can_parse(self, context: EmailParseContext) -> bool:
        """Return true when this parser should handle the email."""

    def parse(self, context: EmailParseContext) -> list[ParsedOpportunity]:
        """Extract every job opportunity found in one email."""
