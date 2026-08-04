from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.cron import DailyIngestionResponse
from app.services.daily_ingestion_service import DailyIngestionService

router = APIRouter()
daily_ingestion_service = DailyIngestionService()
logger = get_logger(__name__)


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
