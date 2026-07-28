from __future__ import annotations

from datetime import datetime

from app.schemas.common import ORMModel


class ProcessedEmailResponse(ORMModel):
    id: int
    gmail_message_id: str
    gmail_thread_id: str | None = None
    source: str | None = None
    sender: str | None = None
    recipients: list[str]
    subject: str | None = None
    received_date: datetime | None = None
    raw_html_body: str | None = None
    plain_text_body: str | None = None
    has_raw_mime: bool
    status: str
    error_summary: str | None = None
    extraction_status: str
    parsed_at: datetime | None = None
    jobs_extracted_count: int
    parsing_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ProcessedEmailListResponse(ORMModel):
    total: int
    items: list[ProcessedEmailResponse]
