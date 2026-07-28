from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.source import IngestionRequest, IngestionResult, SourceInfo
from app.services.ingestion_service import IngestionService
from app.services.source_registry import SourceRegistry

router = APIRouter()
registry = SourceRegistry()
ingestion_service = IngestionService()


@router.get("", response_model=list[SourceInfo])
def list_sources() -> list[SourceInfo]:
    return registry.list_sources()


@router.post("/{source_name}/ingest", response_model=IngestionResult)
async def ingest_source(
    source_name: str,
    payload: IngestionRequest,
    db: Session = Depends(get_db),
) -> IngestionResult:
    try:
        result = await ingestion_service.ingest_source(
            db,
            source_name=source_name,
            raw_html=payload.raw_html,
            limit=payload.limit,
        )
        db.commit()
        db.refresh(result)
        return IngestionResult.model_validate(result)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/ingest-all", response_model=list[IngestionResult])
async def ingest_all_sources(
    payload: IngestionRequest,
    db: Session = Depends(get_db),
) -> list[IngestionResult]:
    results = await ingestion_service.ingest_all(db, limit=payload.limit)
    db.commit()
    for result in results:
        db.refresh(result)
    return [IngestionResult.model_validate(result) for result in results]

