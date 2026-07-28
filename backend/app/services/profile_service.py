from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Profile
from app.schemas.profile import ProfileUpsert


class ProfileService:
    def get_profile(self, db: Session) -> Profile | None:
        return db.scalar(select(Profile).order_by(Profile.id.asc()).limit(1))

    def upsert_profile(self, db: Session, payload: ProfileUpsert) -> Profile:
        profile = self.get_profile(db)
        if profile is None:
            profile = Profile(**payload.model_dump())
            db.add(profile)
        else:
            for field, value in payload.model_dump().items():
                setattr(profile, field, value)
            profile.profile_version += 1
        db.flush()
        db.refresh(profile)
        return profile

