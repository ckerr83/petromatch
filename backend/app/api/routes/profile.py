from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.profile import ProfileResponse, ProfileUpsert
from app.services.profile_service import ProfileService

router = APIRouter()
profile_service = ProfileService()


@router.get("", response_model=ProfileResponse)
def get_profile(db: Session = Depends(get_db)) -> ProfileResponse:
    profile = profile_service.get_profile(db)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return ProfileResponse.model_validate(profile)


@router.put("", response_model=ProfileResponse)
def upsert_profile(payload: ProfileUpsert, db: Session = Depends(get_db)) -> ProfileResponse:
    profile = profile_service.upsert_profile(db, payload)
    db.commit()
    db.refresh(profile)
    return ProfileResponse.model_validate(profile)
