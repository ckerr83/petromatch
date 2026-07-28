from __future__ import annotations

from datetime import date, datetime

from app.schemas.common import ORMModel


class JobResponse(ORMModel):
    id: int
    source: str
    job_title: str | None = None
    company: str | None = None
    location: str | None = None
    job_url: str | None = None
    external_id: str | None = None
    received_date: datetime
    posted_date: date | None = None
    raw_text: str
    dedupe_fingerprint: str | None = None
    processed_email_id: int
    created_at: datetime
    updated_at: datetime


class JobListResponse(ORMModel):
    total: int
    items: list[JobResponse]
