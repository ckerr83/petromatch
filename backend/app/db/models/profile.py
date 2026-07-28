from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.enums import OnshoreOffshore
from app.db.base import Base

JSONVariant = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    target_job_titles: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    target_locations: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    hard_blockers: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_industry_subsections: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    preferred_onshore_offshore: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    include_keywords: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    exclude_keywords: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    scores: Mapped[list["JobScore"]] = relationship(back_populates="profile")

