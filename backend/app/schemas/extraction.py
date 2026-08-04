from __future__ import annotations

from app.schemas.common import ORMModel


class ExtractionRunResponse(ORMModel):
    emails_processed: int
    emails_parsed: int
    emails_partially_parsed: int
    emails_failed: int
    emails_with_no_jobs: int
    jobs_found: int
    jobs_created: int
    duplicates_skipped: int
    errors: list[str] = []


class EmailExtractionResponse(ORMModel):
    email_id: int
    parser: str | None
    extraction_status: str
    jobs_found: int
    jobs_created: int
    duplicates_skipped: int
    failures: int
    errors: list[str] = []
