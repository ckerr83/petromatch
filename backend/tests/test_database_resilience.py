from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import IngestionRun
from app.db.session import engine_kwargs
from app.services.source_ingestion_service import SourceIngestionService
from app.sources.base import SourceAdapter, SourceJob


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return session_factory()


def test_psycopg_engine_disables_automatic_prepared_statements() -> None:
    settings = SimpleNamespace(
        database_url="postgresql+psycopg://user:pass@host:5432/db",
        db_pool_size=1,
        db_max_overflow=2,
        db_pool_recycle_seconds=300,
    )

    kwargs = engine_kwargs(settings)

    assert kwargs["connect_args"]["prepare_threshold"] is None


def test_non_psycopg_engine_does_not_get_psycopg_connect_args() -> None:
    settings = SimpleNamespace(
        database_url="sqlite:///:memory:",
        db_pool_size=1,
        db_max_overflow=2,
        db_pool_recycle_seconds=300,
    )

    kwargs = engine_kwargs(settings)

    assert "connect_args" not in kwargs


def test_source_database_exception_rolls_back_and_records_failed_run(
    monkeypatch,
) -> None:
    db = _session()
    original_rollback = db.rollback
    rollback_calls = 0
    source = OneJobSource()
    service = SourceIngestionService(sources=[source])

    def spy_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    def fail_duplicate_check(db: Session, source_job: SourceJob) -> bool:
        raise RuntimeError('prepared statement "_pg3_0" already exists')

    monkeypatch.setattr(db, "rollback", spy_rollback)
    monkeypatch.setattr(service, "_is_duplicate", fail_duplicate_check)

    result = service.run_source(db, source)
    db.commit()

    runs = db.scalars(select(IngestionRun)).all()
    assert rollback_calls == 1
    assert result.failures == 1
    assert result.jobs_created == 0
    assert len(runs) == 1
    assert runs[0].source == "airswift"
    assert runs[0].status == "failed"
    assert 'prepared statement "_pg3_0" already exists' in (runs[0].error_summary or "")


class OneJobSource(SourceAdapter):
    source = "airswift"
    display_name = "Airswift"

    def fetch_jobs(self) -> list[SourceJob]:
        return [
            SourceJob(
                source="airswift",
                external_id="1278092",
                title="Senior Subsea Structural Engineer",
                company="Airswift",
                location="Kuala Lumpur, Malaysia",
                url="https://www.airswift.com/jobs/senior-subsea-structural-engineer-1278092",
                description="About The Job.",
                source_reference="1278092",
            )
        ]
