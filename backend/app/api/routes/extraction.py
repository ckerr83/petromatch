from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.extraction import ExtractionRunResponse
from app.services.extraction_service import ExtractionService

router = APIRouter()
extraction_service = ExtractionService()


@router.post("/run", response_model=ExtractionRunResponse)
def run_extraction(db: Session = Depends(get_db)) -> ExtractionRunResponse:
    result = extraction_service.run_pending(db)
    db.commit()
    return ExtractionRunResponse.model_validate(result)
