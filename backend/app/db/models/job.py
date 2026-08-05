from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

JSONVariant = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processed_email_id: Mapped[int | None] = mapped_column(
        ForeignKey("processed_emails.id", ondelete="CASCADE"), nullable=True, index=True
    )

    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    job_url: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    dedupe_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    job_title: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    received_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    processed_email: Mapped["ProcessedEmail"] = relationship(back_populates="jobs")
