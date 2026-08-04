from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.db.models import Job, ProcessedEmail
from app.scripts.copy_local_to_supabase import copy_local_to_supabase


def _engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _seed_local(engine: Engine) -> None:
    now = datetime(2026, 8, 4, 8, 0, tzinfo=UTC)
    with engine.begin() as conn:
        conn.execute(
            insert(ProcessedEmail).values(
                id=42,
                gmail_message_id="gmail-42",
                gmail_thread_id="thread-42",
                source="gmail",
                sender="LinkedIn Jobs <jobs-listings@linkedin.com>",
                recipients=["candidate@example.com"],
                subject="LinkedIn job alert",
                received_date=now,
                raw_html_body="<html></html>",
                plain_text_body="Senior Engineer\nPetroCo · Houston, TX",
                raw_mime="raw mime",
                headers={"From": "LinkedIn Jobs <jobs-listings@linkedin.com>"},
                status="ingested",
                extraction_status="parsed",
                parsed_at=now,
                jobs_extracted_count=1,
                parsing_error=None,
                created_at=now,
                updated_at=now,
            )
        )
        conn.execute(
            insert(Job).values(
                id=125,
                processed_email_id=42,
                source="linkedin",
                external_id="1234567890",
                job_url="https://www.linkedin.com/jobs/view/1234567890/",
                dedupe_fingerprint="fingerprint-1",
                job_title="Senior Engineer",
                company="PetroCo",
                location="Houston, TX",
                posted_date=None,
                received_date=now,
                raw_text="Senior Engineer\nPetroCo · Houston, TX",
                source_payload={"parser": "linkedin"},
                created_at=now,
                updated_at=now,
            )
        )


def test_dry_run_makes_no_changes() -> None:
    local_engine = _engine()
    supabase_engine = _engine()
    _seed_local(local_engine)

    stats = copy_local_to_supabase(
        local_engine=local_engine,
        supabase_engine=supabase_engine,
        apply=False,
    )

    assert {stat.table_name: stat.inserted for stat in stats}["processed_emails"] == 1
    assert {stat.table_name: stat.inserted for stat in stats}["jobs"] == 1
    with supabase_engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(ProcessedEmail)) == 0
        assert conn.scalar(select(func.count()).select_from(Job)) == 0
        assert conn.execute(select(ProcessedEmail)).first() is None
        assert conn.execute(select(Job)).first() is None


def test_apply_and_rerun_does_not_duplicate_data() -> None:
    local_engine = _engine()
    supabase_engine = _engine()
    _seed_local(local_engine)

    first = copy_local_to_supabase(local_engine=local_engine, supabase_engine=supabase_engine, apply=True)
    second = copy_local_to_supabase(local_engine=local_engine, supabase_engine=supabase_engine, apply=True)

    assert {stat.table_name: stat.inserted for stat in first}["processed_emails"] == 1
    assert {stat.table_name: stat.inserted for stat in first}["jobs"] == 1
    assert {stat.table_name: stat.skipped for stat in second}["processed_emails"] == 1
    assert {stat.table_name: stat.skipped for stat in second}["jobs"] == 1
    with supabase_engine.connect() as conn:
        assert len(conn.execute(select(ProcessedEmail)).all()) == 1
        assert len(conn.execute(select(Job)).all()) == 1


def test_foreign_key_relationships_are_preserved() -> None:
    local_engine = _engine()
    supabase_engine = _engine()
    _seed_local(local_engine)

    copy_local_to_supabase(local_engine=local_engine, supabase_engine=supabase_engine, apply=True)

    with supabase_engine.connect() as conn:
        job = conn.execute(select(Job.__table__)).mappings().one()
        email = conn.execute(
            select(ProcessedEmail.__table__).where(ProcessedEmail.id == job["processed_email_id"])
        ).mappings().one()

    assert job["id"] == 125
    assert job["processed_email_id"] == 42
    assert email["gmail_message_id"] == "gmail-42"


def test_future_ids_continue_above_preserved_ids_after_copy() -> None:
    local_engine = _engine()
    supabase_engine = _engine()
    _seed_local(local_engine)

    copy_local_to_supabase(local_engine=local_engine, supabase_engine=supabase_engine, apply=True)

    with supabase_engine.begin() as conn:
        result = conn.execute(
            insert(ProcessedEmail).values(
                gmail_message_id="gmail-new",
                recipients=[],
                status="ingested",
                extraction_status="pending",
                jobs_extracted_count=0,
                created_at=datetime(2026, 8, 4, 9, 0, tzinfo=UTC),
                updated_at=datetime(2026, 8, 4, 9, 0, tzinfo=UTC),
            )
        )
        inserted_pk = result.inserted_primary_key[0]

    assert inserted_pk > 42


def test_job_is_skipped_when_matching_email_exists_with_different_primary_key() -> None:
    local_engine = _engine()
    supabase_engine = _engine()
    _seed_local(local_engine)
    now = datetime(2026, 8, 4, 8, 0, tzinfo=UTC)
    with supabase_engine.begin() as conn:
        conn.execute(
            insert(ProcessedEmail).values(
                id=99,
                gmail_message_id="gmail-42",
                recipients=[],
                status="ingested",
                extraction_status="pending",
                jobs_extracted_count=0,
                created_at=now,
                updated_at=now,
            )
        )

    stats = copy_local_to_supabase(local_engine=local_engine, supabase_engine=supabase_engine, apply=True)

    assert {stat.table_name: stat.skipped for stat in stats}["processed_emails"] == 1
    assert {stat.table_name: stat.skipped for stat in stats}["jobs"] == 1
    with supabase_engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Job)) == 0
