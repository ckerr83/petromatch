from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.api.routes import cron as cron_routes
from app.core.config import get_settings
from app.db.base import Base
from app.db.models import Job, ProcessedEmail
from app.main import app
from app.services.daily_ingestion_service import DailyIngestionResult, DailyIngestionService
from app.services.extraction_service import ExtractionService
from app.services.gmail_client import GmailClient, GmailCredentialsError, credentials_from_token_json
from app.services.gmail_ingestion_service import GmailIngestionService
from app.services.source_ingestion_service import SourceIngestionService


class StubDailyIngestionService:
    def __init__(self) -> None:
        self.calls = 0

    def run_once(self, db: Session) -> DailyIngestionResult:
        self.calls += 1
        return DailyIngestionResult(
            emails_found=0,
            emails_processed=0,
            emails_skipped=0,
            jobs_found=0,
            jobs_created=0,
            duplicates_skipped=0,
            errors=[],
        )


class FakeGmailClient:
    def __init__(self, messages: dict[str, dict[str, Any]]) -> None:
        self.messages = messages

    def list_message_ids(self, *, query: str, max_results: int) -> list[str]:
        return list(self.messages.keys())[:max_results]

    def get_message_full(self, message_id: str) -> dict[str, Any]:
        return self.messages[message_id]["full"]

    def get_message_raw_mime(self, message_id: str) -> str | None:
        return self.messages[message_id]["raw"]


@pytest.fixture()
def sqlite_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(sqlite_session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CRON_SECRET", "test-secret")
    get_settings.cache_clear()

    def override_db():
        yield sqlite_session

    stub = StubDailyIngestionService()
    monkeypatch.setattr(cron_routes, "daily_ingestion_service", stub)
    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_health_endpoint_succeeds(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cron_endpoint_rejects_missing_authorization(client: TestClient) -> None:
    response = client.get("/api/v1/cron/daily-ingestion")

    assert response.status_code == 401


def test_cron_endpoint_rejects_incorrect_secret(client: TestClient) -> None:
    response = client.get("/api/v1/cron/daily-ingestion", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401


def test_cron_endpoint_accepts_correct_secret(client: TestClient) -> None:
    response = client.get("/api/v1/cron/daily-ingestion", headers={"Authorization": "Bearer test-secret"})

    assert response.status_code == 200
    assert response.json()["emails_found"] == 0


def test_daily_ingestion_is_idempotent_for_identical_gmail_messages(sqlite_session: Session) -> None:
    service = _daily_service_with_messages(
        {
            "gmail-1": _gmail_message(
                message_id="gmail-1",
                url="https://www.linkedin.com/jobs/view/1234567890/",
                title="Senior Drilling Engineer",
            )
        }
    )

    first = service.run_once(sqlite_session)
    sqlite_session.commit()
    second = service.run_once(sqlite_session)
    sqlite_session.commit()

    assert first.emails_processed == 1
    assert first.jobs_created == 1
    assert second.emails_processed == 0
    assert second.emails_skipped == 1
    assert second.jobs_created == 0
    assert len(sqlite_session.scalars(select(ProcessedEmail)).all()) == 1
    assert len(sqlite_session.scalars(select(Job)).all()) == 1


def test_daily_ingestion_with_no_new_gmail_messages_succeeds(sqlite_session: Session) -> None:
    service = _daily_service_with_messages({})

    result = service.run_once(sqlite_session)

    assert result.emails_found == 0
    assert result.emails_processed == 0
    assert result.jobs_found == 0
    assert result.jobs_created == 0
    assert result.errors == []


def test_duplicate_jobs_are_skipped(sqlite_session: Session) -> None:
    service = _daily_service_with_messages(
        {
            "gmail-1": _gmail_message(
                message_id="gmail-1",
                url="https://www.linkedin.com/jobs/view/1234567890/",
                title="Senior Drilling Engineer",
            ),
            "gmail-2": _gmail_message(
                message_id="gmail-2",
                url="https://www.linkedin.com/jobs/view/1234567890/",
                title="Senior Drilling Engineer",
            ),
        }
    )

    result = service.run_once(sqlite_session)
    sqlite_session.commit()

    assert result.emails_processed == 2
    assert result.jobs_found == 2
    assert result.jobs_created == 1
    assert result.duplicates_skipped == 1
    assert len(sqlite_session.scalars(select(Job)).all()) == 1


def test_gmail_token_json_is_loaded_correctly() -> None:
    credentials = credentials_from_token_json(
        json.dumps(
            {
                "token": "access-token",
                "refresh_token": "refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            }
        ),
        google_client_id="client-id",
        google_client_secret="client-secret",
    )

    assert credentials.token == "access-token"
    assert credentials.refresh_token == "refresh-token"
    assert credentials.client_id == "client-id"


def test_invalid_gmail_token_json_produces_clear_error() -> None:
    with pytest.raises(GmailCredentialsError, match="not valid JSON"):
        credentials_from_token_json("{not json", google_client_id="client-id", google_client_secret="client-secret")


def test_local_token_file_loading_still_works(tmp_path: Path) -> None:
    token_path = tmp_path / "gmail_token.json"
    token_path.write_text(
        json.dumps(
            {
                "token": "access-token",
                "refresh_token": "refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
                "expiry": "2999-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    credentials = GmailClient(token_path=token_path)._load_credentials()

    assert credentials.token == "access-token"
    assert credentials.valid is True


def test_gmail_list_message_ids_uses_profile_diagnostics_without_live_gmail(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_service = FakeGmailService()
    client = GmailClient()
    monkeypatch.setattr(client, "build_service", lambda: fake_service)

    message_ids = client.list_message_ids(query="is:unread", max_results=50)

    assert message_ids == ["message-1", "message-2"]
    assert fake_service.profile_requested is True


def _daily_service_with_messages(messages: dict[str, dict[str, Any]]) -> DailyIngestionService:
    return DailyIngestionService(
        gmail_ingestion_service=GmailIngestionService(gmail_client=FakeGmailClient(messages)),
        extraction_service=ExtractionService(),
        source_ingestion_service=SourceIngestionService(sources=[]),
    )


def _gmail_message(*, message_id: str, url: str, title: str) -> dict[str, Any]:
    html = f"""
    <html><body>
      <div>
        <a href="{url}">{title}</a>
        <span>PetroCo · Houston, TX</span>
      </div>
    </body></html>
    """
    raw = "\n".join(
        [
            "From: LinkedIn Jobs <jobs-listings@linkedin.com>",
            "To: candidate@example.com",
            "Subject: LinkedIn job alert",
            "Date: Tue, 28 Jul 2026 10:00:00 +0000",
            "MIME-Version: 1.0",
            "Content-Type: text/html; charset=utf-8",
            "",
            html,
        ]
    )
    return {
        "full": {
            "id": message_id,
            "threadId": f"thread-{message_id}",
            "internalDate": str(int(datetime(2026, 7, 28, 10, 0, tzinfo=UTC).timestamp() * 1000)),
            "payload": {
                "mimeType": "text/html",
                "headers": [
                    {"name": "From", "value": "LinkedIn Jobs <jobs-listings@linkedin.com>"},
                    {"name": "To", "value": "candidate@example.com"},
                    {"name": "Subject", "value": "LinkedIn job alert"},
                    {"name": "Date", "value": "Tue, 28 Jul 2026 10:00:00 +0000"},
                ],
                "body": {"data": ""},
            },
        },
        "raw": raw,
    }


class FakeGmailService:
    def __init__(self) -> None:
        self.profile_requested = False

    def users(self) -> "FakeGmailService":
        return self

    def getProfile(self, *, userId: str) -> "FakeGmailService":
        assert userId == "me"
        self.profile_requested = True
        self._response = {"emailAddress": "petromatch@example.com"}
        return self

    def messages(self) -> "FakeGmailService":
        return self

    def list(self, *, userId: str, q: str, maxResults: int) -> "FakeGmailService":
        assert userId == "me"
        assert q == "is:unread"
        assert maxResults == 50
        self._response = {"messages": [{"id": "message-1"}, {"id": "message-2"}], "resultSizeEstimate": 2}
        return self

    def list_next(self, request: Any, response: dict[str, Any]) -> None:
        return None

    def execute(self) -> dict[str, Any]:
        return self._response
