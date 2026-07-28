from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Job, ProcessedEmail
from app.services.extraction_service import ExtractionService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return session_factory()


def test_extraction_creates_jobs_and_skips_duplicates_on_second_run() -> None:
    db = _session()
    email = ProcessedEmail(
        gmail_message_id="gmail-1",
        gmail_thread_id="thread-1",
        source="gmail",
        sender="jobs-listings@linkedin.com",
        recipients=["candidate@example.com"],
        subject="LinkedIn job alert",
        received_date=datetime(2026, 7, 28, 10, 0, tzinfo=UTC),
        raw_html_body="""
        <div>
          <a href="https://www.linkedin.com/jobs/view/1234567890/?trk=email">Senior Drilling Engineer</a>
          <span>PetroCo</span>
          <span>Houston, TX</span>
        </div>
        """,
        status="ingested",
        extraction_status="pending",
    )
    db.add(email)
    db.commit()

    first = ExtractionService().run_pending(db)
    db.commit()

    assert first.emails_processed == 1
    assert first.jobs_created == 1
    assert first.duplicates_skipped == 0
    assert db.scalar(select(Job).where(Job.external_id == "1234567890")) is not None

    email.extraction_status = "pending"
    db.flush()
    second = ExtractionService().run_pending(db)
    db.commit()

    assert second.jobs_created == 0
    assert second.duplicates_skipped == 1
    assert len(db.scalars(select(Job)).all()) == 1
