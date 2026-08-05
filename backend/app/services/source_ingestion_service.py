from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import IngestionRun, Job
from app.sources import AirswiftSource, SourceAdapter, SourceJob
from app.utils.fingerprints import build_dedupe_fingerprint
from app.utils.text import normalize_whitespace

logger = get_logger(__name__)


@dataclass(frozen=True)
class SourceIngestionResult:
    source: str
    jobs_found: int
    jobs_created: int
    duplicates_skipped: int
    failures: int
    errors: list[str]


class SourceIngestionService:
    def __init__(self, sources: list[SourceAdapter] | None = None) -> None:
        self.sources = sources if sources is not None else [AirswiftSource()]

    def run_all(self, db: Session) -> list[SourceIngestionResult]:
        return [self.run_source(db, source) for source in self.sources]

    def run_source(self, db: Session, source: SourceAdapter) -> SourceIngestionResult:
        run = IngestionRun(source=source.source, status="started")
        db.add(run)
        db.flush()

        jobs_found = 0
        jobs_created = 0
        duplicates_skipped = 0
        failures = 0
        errors: list[str] = []

        try:
            logger.info("source_ingestion_started", source=source.source)
            source_jobs = source.fetch_jobs()
            jobs_found = len(source_jobs)
            for source_job in source_jobs:
                try:
                    if self._is_duplicate(db, source_job):
                        duplicates_skipped += 1
                        continue
                    source_job = source.enrich_job(source_job)
                    if self._is_duplicate(db, source_job):
                        duplicates_skipped += 1
                        continue
                    db.add(_job_from_source(source_job))
                    db.flush()
                    jobs_created += 1
                except Exception as exc:  # noqa: BLE001
                    failures += 1
                    error = f"source={source.source} external_id={source_job.external_id}: {type(exc).__name__}: {exc}"
                    errors.append(error)
                    logger.warning(
                        "source_job_ingestion_failed",
                        source=source.source,
                        external_id=source_job.external_id,
                        error=str(exc),
                    )
            run.status = "completed" if failures == 0 else "completed_with_errors"
        except Exception as exc:  # noqa: BLE001
            failures += 1
            errors.append(f"source={source.source}: {type(exc).__name__}: {exc}")
            run.status = "failed"
            run.error_summary = str(exc)
            logger.warning("source_ingestion_failed", source=source.source, error=str(exc))
        finally:
            run.jobs_created = jobs_created
            run.jobs_skipped_duplicate = duplicates_skipped
            run.jobs_failed = failures
            run.finished_at = datetime.now(UTC)
            logger.info(
                "source_ingestion_completed",
                source=source.source,
                jobs_found=jobs_found,
                jobs_created=jobs_created,
                duplicates_skipped=duplicates_skipped,
                failures=failures,
            )

        return SourceIngestionResult(
            source=source.source,
            jobs_found=jobs_found,
            jobs_created=jobs_created,
            duplicates_skipped=duplicates_skipped,
            failures=failures,
            errors=errors,
        )

    def _is_duplicate(self, db: Session, source_job: SourceJob) -> bool:
        checks = []
        if source_job.external_id:
            checks.append((Job.source == source_job.source) & (Job.external_id == source_job.external_id))
        if source_job.url:
            checks.append(Job.job_url == source_job.url)
        fingerprint = build_dedupe_fingerprint(source_job.title, source_job.company, source_job.location)
        if fingerprint:
            checks.append(Job.dedupe_fingerprint == fingerprint)
        if not checks:
            return False
        return db.scalar(select(Job.id).where(or_(*checks)).limit(1)) is not None


def _job_from_source(source_job: SourceJob) -> Job:
    title = normalize_whitespace(source_job.title)
    company = normalize_whitespace(source_job.company)
    location = normalize_whitespace(source_job.location)
    description = normalize_whitespace(source_job.description) or source_job.title

    return Job(
        processed_email_id=None,
        source=source_job.source,
        external_id=normalize_whitespace(source_job.external_id) or source_job.url,
        job_url=source_job.url,
        dedupe_fingerprint=build_dedupe_fingerprint(title, company, location),
        job_title=title,
        company=company,
        location=location,
        posted_date=source_job.posted_date,
        received_date=datetime.now(UTC),
        raw_text=description,
        source_payload={
            "employment_type": source_job.employment_type,
            "salary": source_job.salary,
            "source_reference": source_job.source_reference,
            "raw_metadata": source_job.raw_metadata,
        },
    )
