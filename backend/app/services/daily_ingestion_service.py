from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.extraction_service import ExtractionService
from app.services.gmail_ingestion_service import GmailIngestionService

logger = get_logger(__name__)


@dataclass(frozen=True)
class DailyIngestionResult:
    emails_found: int
    emails_processed: int
    emails_skipped: int
    jobs_found: int
    jobs_created: int
    duplicates_skipped: int
    errors: list[str]


class DailyIngestionService:
    def __init__(
        self,
        *,
        gmail_ingestion_service: GmailIngestionService | None = None,
        extraction_service: ExtractionService | None = None,
    ) -> None:
        self.gmail_ingestion_service = gmail_ingestion_service or GmailIngestionService()
        self.extraction_service = extraction_service or ExtractionService()

    def run_once(self, db: Session) -> DailyIngestionResult:
        logger.info("daily_ingestion_started")
        gmail_result = self.gmail_ingestion_service.run_once(db)
        extraction_result = self.extraction_service.run_pending(db)
        errors = [*gmail_result.errors, *extraction_result.errors]
        result = DailyIngestionResult(
            emails_found=gmail_result.emails_discovered,
            emails_processed=gmail_result.new_emails_stored,
            emails_skipped=gmail_result.duplicates_skipped,
            jobs_found=extraction_result.jobs_found,
            jobs_created=extraction_result.jobs_created,
            duplicates_skipped=extraction_result.duplicates_skipped,
            errors=errors,
        )
        logger.info(
            "daily_ingestion_completed",
            emails_found=result.emails_found,
            emails_processed=result.emails_processed,
            emails_skipped=result.emails_skipped,
            jobs_found=result.jobs_found,
            jobs_created=result.jobs_created,
            duplicates_skipped=result.duplicates_skipped,
            errors=len(result.errors),
        )
        return result
