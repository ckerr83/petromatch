from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.cron import AirswiftCronResponse, DailyIngestionResponse, GmailCronResponse
from app.services.daily_ingestion_service import DailyIngestionService
from app.services.extraction_service import ExtractionService
from app.services.gmail_ingestion_service import GmailIngestionService
from app.services.source_ingestion_service import SourceIngestionService
from app.sources import AirswiftSource

router = APIRouter()
daily_ingestion_service = DailyIngestionService()
gmail_ingestion_service = GmailIngestionService()
extraction_service = ExtractionService()
airswift_ingestion_service = SourceIngestionService(sources=[AirswiftSource()])
logger = get_logger(__name__)


@router.get("/gmail", response_model=GmailCronResponse)
def run_gmail_cron(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> GmailCronResponse:
    _verify_cron_secret(authorization)
    try:
        logger.info("gmail_cron_started")
        gmail_result = gmail_ingestion_service.run_once(db)
        extraction_result = extraction_service.run_pending(db)
        response = GmailCronResponse(
            emails_found=gmail_result.emails_discovered,
            emails_processed=gmail_result.new_emails_stored,
            emails_skipped=gmail_result.duplicates_skipped,
            jobs_found=extraction_result.jobs_found,
            jobs_created=extraction_result.jobs_created,
            duplicates_skipped=extraction_result.duplicates_skipped,
            errors=[*gmail_result.errors, *extraction_result.errors],
        )
        db.commit()
        logger.info(
            "gmail_cron_completed",
            emails_found=response.emails_found,
            emails_processed=response.emails_processed,
            emails_skipped=response.emails_skipped,
            jobs_found=response.jobs_found,
            jobs_created=response.jobs_created,
            duplicates_skipped=response.duplicates_skipped,
            errors=len(response.errors),
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("gmail_cron_unexpected_failure", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gmail cron ingestion failed. Check server logs for details.",
        ) from exc


@router.get("/airswift", response_model=AirswiftCronResponse)
def run_airswift_cron(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AirswiftCronResponse:
    _verify_cron_secret(authorization)
    try:
        logger.info("airswift_cron_started")
        result = airswift_ingestion_service.run_all(db)[0]
        response = AirswiftCronResponse(
            jobs_discovered=result.jobs_found,
            already_existing=result.already_existing,
            new_jobs_processed=result.new_jobs_processed,
            jobs_created=result.jobs_created,
            failures=result.failures,
            remaining_unprocessed_new_jobs=result.remaining_unprocessed_new_jobs,
            stopped_due_to_budget=result.stopped_due_to_budget,
            errors=result.errors,
        )
        db.commit()
        logger.info(
            "airswift_cron_completed",
            jobs_discovered=response.jobs_discovered,
            already_existing=response.already_existing,
            new_jobs_processed=response.new_jobs_processed,
            jobs_created=response.jobs_created,
            failures=response.failures,
            remaining_unprocessed_new_jobs=response.remaining_unprocessed_new_jobs,
            stopped_due_to_budget=response.stopped_due_to_budget,
            errors=len(response.errors),
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("airswift_cron_unexpected_failure", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Airswift cron ingestion failed. Check server logs for details.",
        ) from exc


# Legacy compatibility endpoint. New scheduling should use /cron/gmail and /cron/airswift
# so Vercel functions stay comfortably inside their runtime budget.
@router.get("/daily-ingestion", response_model=DailyIngestionResponse)
def run_daily_ingestion_get(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> DailyIngestionResponse:
    return _run_daily_ingestion(authorization=authorization, db=db)


@router.post("/daily-ingestion", response_model=DailyIngestionResponse)
def run_daily_ingestion_post(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> DailyIngestionResponse:
    return _run_daily_ingestion(authorization=authorization, db=db)


def _run_daily_ingestion(*, authorization: str | None, db: Session) -> DailyIngestionResponse:
    _verify_cron_secret(authorization)
    try:
        result = daily_ingestion_service.run_once(db)
        db.commit()
        return DailyIngestionResponse.model_validate(result)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("daily_ingestion_unexpected_failure", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Daily ingestion failed. Check server logs for details.",
        ) from exc


def _verify_cron_secret(authorization: str | None) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.cron_secret}" if settings.cron_secret else None
    if not expected or authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
