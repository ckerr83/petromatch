from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

JSONVariant = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class ProcessedEmail(Base):
    __tablename__ = "processed_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sender: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipients: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    raw_html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    plain_text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_mime: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ingested", index=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    jobs_extracted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    jobs: Mapped[list["Job"]] = relationship(back_populates="processed_email", cascade="all, delete-orphan")

    @property
    def has_raw_mime(self) -> bool:
        return bool(self.raw_mime)
