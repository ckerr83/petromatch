from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class ExtractedJob:
    source_name: str
    source_url: str
    external_job_id: str | None
    title: str | None
    company: str | None = None
    location: str | None = None
    employment_type: str | None = None
    posted_date: date | None = None
    raw_description: str | None = None
    recruiter_name: str | None = None
    source_payload: dict[str, Any] = field(default_factory=dict)

