from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ProfileBase(BaseModel):
    cv_text: str | None = None
    cv_filename: str | None = None
    target_job_titles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    hard_blockers: list[str] = Field(default_factory=list)
    years_of_experience: int | None = None
    preferred_industry_subsections: list[str] = Field(default_factory=list)
    preferred_onshore_offshore: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)


class ProfileUpsert(ProfileBase):
    pass


class ProfileResponse(ProfileBase, ORMModel):
    id: int
    profile_version: int
    created_at: datetime
    updated_at: datetime

