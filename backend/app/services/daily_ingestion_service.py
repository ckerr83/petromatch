from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.extraction_service import ExtractionService
from app.services.gmail_ingestion_service import GmailIngestionService
from app.services.source_ingestion_service import SourceIngestionResult, SourceIngestionService

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
    gmail: dict[str, int] | None = None
    airswift: dict[str, int] | None = None
    sources: dict[str, dict[str, int]] | None = None


class DailyIngestionService:
    def __init__(
        self,
        *,
        gmail_ingestion_service: GmailIngestionService | None = None,
        extraction_service: ExtractionService | None = None,
        source_ingestion_service: SourceIngestionService | None = None,
    ) -> None:
        self.gmail_ingestion_service = gmail_ingestion_service or GmailIngestionService()
        self.extraction_service = extraction_service or ExtractionService()
        self.source_ingestion_service = source_ingestion_service or SourceIngestionService()

    def run_once(self, db: Session) -> DailyIngestionResult:
        logger.info("daily_ingestion_started")
        gmail_result = self.gmail_ingestion_service.run_once(db)
        extraction_result = self.extraction_service.run_pending(db)
        source_results = self.source_ingestion_service.run_all(db)
        errors = [
            *gmail_result.errors,
            *extraction_result.errors,
            *(error for source_result in source_results for error in source_result.errors),
        ]
        gmail_jobs_created = extraction_result.jobs_created
        source_jobs_found = sum(source_result.jobs_found for source_result in source_results)
        source_jobs_created = sum(source_result.jobs_created for source_result in source_results)
        source_duplicates = sum(source_result.duplicates_skipped for source_result in source_results)
        sources_summary = _source_summary(source_results)
        result = DailyIngestionResult(
            emails_found=gmail_result.emails_discovered,
            emails_processed=gmail_result.new_emails_stored,
            emails_skipped=gmail_result.duplicates_skipped,
            jobs_found=extraction_result.jobs_found + source_jobs_found,
            jobs_created=gmail_jobs_created + source_jobs_created,
            duplicates_skipped=extraction_result.duplicates_skipped + source_duplicates,
            errors=errors,
            gmail={
                "emails_found": gmail_result.emails_discovered,
                "jobs_created": gmail_jobs_created,
            },
            airswift=sources_summary.get("airswift"),
            sources=sources_summary,
        )
        logger.info(
            "daily_ingestion_completed",
            emails_found=result.emails_found,
            emails_processed=result.emails_processed,
            emails_skipped=result.emails_skipped,
            jobs_found=result.jobs_found,
            jobs_created=result.jobs_created,
            duplicates_skipped=result.duplicates_skipped,
            source_jobs_found=source_jobs_found,
            source_jobs_created=source_jobs_created,
            source_duplicates_skipped=source_duplicates,
            errors=len(result.errors),
        )
        return result


def _source_summary(source_results: list[SourceIngestionResult]) -> dict[str, dict[str, int]]:
    return {
        source_result.source: {
            "jobs_found": source_result.jobs_found,
            "jobs_created": source_result.jobs_created,
            "duplicates_skipped": source_result.duplicates_skipped,
        }
        for source_result in source_results
    }
