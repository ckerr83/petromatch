from __future__ import annotations

from app.schemas.common import ORMModel


class GmailIngestionRunResponse(ORMModel):
    emails_discovered: int
    new_emails_stored: int
    duplicates_skipped: int
    failures: int
    errors: list[str] = []
