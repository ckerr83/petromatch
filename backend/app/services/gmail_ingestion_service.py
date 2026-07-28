from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email import message_from_string
from email.policy import default
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import IngestionRun, ProcessedEmail
from app.services.gmail_client import GmailClient


@dataclass(frozen=True)
class GmailIngestionResult:
    emails_discovered: int
    new_emails_stored: int
    duplicates_skipped: int
    failures: int


class GmailIngestionService:
    def __init__(self, gmail_client: GmailClient | None = None) -> None:
        self.gmail_client = gmail_client or GmailClient()

    def run_once(self, db: Session) -> GmailIngestionResult:
        settings = get_settings()
        run = IngestionRun(source="gmail", status="started")
        db.add(run)
        db.flush()

        discovered = 0
        stored = 0
        skipped = 0
        failures = 0

        try:
            message_ids = self.gmail_client.list_message_ids(
                query=settings.gmail_query,
                max_results=settings.gmail_max_results,
            )
            discovered = len(message_ids)

            existing_ids = set(
                db.scalars(
                    select(ProcessedEmail.gmail_message_id).where(
                        ProcessedEmail.gmail_message_id.in_(message_ids)
                    )
                ).all()
            )

            for message_id in message_ids:
                if message_id in existing_ids:
                    skipped += 1
                    continue

                try:
                    email_record = self._fetch_and_build_record(message_id)
                    db.add(email_record)
                    db.flush()
                    stored += 1
                except Exception as exc:  # noqa: BLE001
                    db.add(
                        ProcessedEmail(
                            gmail_message_id=message_id,
                            status="failed",
                            recipients=[],
                            error_summary=str(exc),
                        )
                    )
                    db.flush()
                    failures += 1

            run.status = "completed" if failures == 0 else "completed_with_errors"
        except Exception as exc:  # noqa: BLE001
            failures += 1
            run.status = "failed"
            run.error_summary = str(exc)
        finally:
            run.emails_seen = discovered
            run.emails_processed = stored
            run.emails_skipped = skipped
            run.jobs_created = 0
            run.jobs_skipped_duplicate = 0
            run.jobs_failed = 0
            run.finished_at = datetime.now(UTC)

        return GmailIngestionResult(
            emails_discovered=discovered,
            new_emails_stored=stored,
            duplicates_skipped=skipped,
            failures=failures,
        )

    def _fetch_and_build_record(self, message_id: str) -> ProcessedEmail:
        full_message = self.gmail_client.get_message_full(message_id)
        raw_mime = self.gmail_client.get_message_raw_mime(message_id)

        headers = _headers_from_payload(full_message.get("payload", {}))
        text_body, html_body = _extract_bodies(raw_mime, full_message.get("payload", {}))
        received_date = _received_datetime(full_message, headers)

        return ProcessedEmail(
            gmail_message_id=full_message["id"],
            gmail_thread_id=full_message.get("threadId"),
            source="gmail",
            sender=_header_value(headers, "From"),
            recipients=_recipient_values(headers),
            subject=_header_value(headers, "Subject"),
            received_date=received_date,
            raw_html_body=html_body,
            plain_text_body=text_body,
            raw_mime=raw_mime,
            headers=headers,
            status="ingested",
        )


def _headers_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header in payload.get("headers", []):
        name = header.get("name")
        value = header.get("value")
        if name and value is not None:
            headers[name] = value
    return headers


def _header_value(headers: dict[str, str], name: str) -> str | None:
    for header_name, value in headers.items():
        if header_name.lower() == name.lower():
            return value
    return None


def _recipient_values(headers: dict[str, str]) -> list[str]:
    raw_values = [
        value
        for name, value in headers.items()
        if name.lower() in {"to", "cc", "bcc"}
    ]
    addresses = [address for _, address in getaddresses(raw_values) if address]
    return addresses


def _received_datetime(full_message: dict[str, Any], headers: dict[str, str]) -> datetime | None:
    date_header = _header_value(headers, "Date")
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
        except (TypeError, ValueError):
            pass

    internal_date = full_message.get("internalDate")
    if internal_date:
        try:
            return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
        except (TypeError, ValueError):
            return None
    return None


def _extract_bodies(raw_mime: str | None, payload: dict[str, Any]) -> tuple[str | None, str | None]:
    if raw_mime:
        parsed_message = message_from_string(raw_mime, policy=default)
        text_part = parsed_message.get_body(preferencelist=("plain",))
        html_part = parsed_message.get_body(preferencelist=("html",))
        text_body = text_part.get_content() if text_part else None
        html_body = html_part.get_content() if html_part else None
        return text_body, html_body

    return _extract_body_from_payload(payload, "text/plain"), _extract_body_from_payload(payload, "text/html")


def _extract_body_from_payload(payload: dict[str, Any], mime_type: str) -> str | None:
    if payload.get("mimeType") == mime_type:
        body_data = payload.get("body", {}).get("data")
        if body_data:
            from app.services.gmail_client import _decode_base64url

            return _decode_base64url(body_data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        value = _extract_body_from_payload(part, mime_type)
        if value:
            return value
    return None
