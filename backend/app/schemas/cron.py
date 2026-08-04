from __future__ import annotations

from app.schemas.common import ORMModel


class DailyIngestionResponse(ORMModel):
    emails_found: int
    emails_processed: int
    emails_skipped: int
    jobs_found: int
    jobs_created: int
    duplicates_skipped: int
    errors: list[str]
