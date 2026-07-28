from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.ingestion import GmailIngestionRunResponse
from app.services.gmail_ingestion_service import GmailIngestionService

router = APIRouter()
gmail_ingestion_service = GmailIngestionService()


@router.post("/gmail/run", response_model=GmailIngestionRunResponse)
def run_gmail_ingestion(db: Session = Depends(get_db)) -> GmailIngestionRunResponse:
    result = gmail_ingestion_service.run_once(db)
    db.commit()
    return GmailIngestionRunResponse.model_validate(result)
