from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import ProcessedEmail
from app.schemas.email import ProcessedEmailListResponse, ProcessedEmailResponse
from app.schemas.extraction import EmailExtractionResponse
from app.services.extraction_service import ExtractionService

router = APIRouter()
extraction_service = ExtractionService()


@router.get("", response_model=ProcessedEmailListResponse)
def list_processed_emails(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ProcessedEmailListResponse:
    emails = db.scalars(
        select(ProcessedEmail)
        .order_by(ProcessedEmail.received_date.desc().nullslast(), ProcessedEmail.id.desc())
        .limit(limit)
    ).all()
    items = [ProcessedEmailResponse.model_validate(email) for email in emails]
    return ProcessedEmailListResponse(total=len(items), items=items)


@router.post("/{email_id}/extract", response_model=EmailExtractionResponse)
def extract_email(email_id: int, db: Session = Depends(get_db)) -> EmailExtractionResponse:
    result = extraction_service.extract_email_by_id(db, email_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found.")
    db.commit()
    return EmailExtractionResponse.model_validate(result)
