from __future__ import annotations

from typing import Any

from app.schemas.common import ORMModel


class DailyIngestionResponse(ORMModel):
    emails_found: int
    emails_processed: int
    emails_skipped: int
    jobs_found: int
    jobs_created: int
    duplicates_skipped: int
    errors: list[str]
    gmail: dict[str, int] | None = None
    airswift: dict[str, Any] | None = None
    sources: dict[str, dict[str, Any]] | None = None


class GmailCronResponse(ORMModel):
    emails_found: int
    emails_processed: int
    emails_skipped: int
    jobs_found: int
    jobs_created: int
    duplicates_skipped: int
    errors: list[str]


class AirswiftCronResponse(ORMModel):
    jobs_discovered: int
    already_existing: int
    new_jobs_processed: int
    jobs_created: int
    failures: int
    remaining_unprocessed_new_jobs: int
    stopped_due_to_budget: bool
    errors: list[str]
