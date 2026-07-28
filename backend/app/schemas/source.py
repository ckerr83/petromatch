from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    display_name: str
    base_url: str
    supports_live_fetch: bool = True
    notes: str | None = None


class IngestionRequest(BaseModel):
    raw_html: str | None = None
    limit: int = 50


class IngestionResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_name: str
    status: str
    jobs_seen: int
    jobs_created: int
    jobs_updated: int
    jobs_failed: int
    error_summary: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
