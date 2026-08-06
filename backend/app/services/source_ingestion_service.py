from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
    already_existing: int = 0
    new_jobs_processed: int = 0
    remaining_unprocessed_new_jobs: int = 0
    stopped_due_to_budget: bool = False


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
        already_existing = 0
        new_jobs_processed = 0
        remaining_unprocessed_new_jobs = 0
        stopped_due_to_budget = False
        errors: list[str] = []
        run_recorded_after_rollback = False

        try:
            logger.info("source_ingestion_started", source=source.source)
            source_jobs = source.fetch_jobs()
            jobs_found = len(source_jobs)
            new_source_jobs: list[SourceJob] = []
            for source_job in source_jobs:
                if self._is_duplicate(db, source_job):
                    duplicates_skipped += 1
                    already_existing += 1
                    continue
                new_source_jobs.append(source_job)

            max_new_jobs = _max_new_jobs_for_source(source.source)
            time_budget_seconds = _time_budget_for_source(source.source)
            deadline = time.monotonic() + time_budget_seconds if time_budget_seconds else None
            remaining_unprocessed_new_jobs = max(0, len(new_source_jobs) - max_new_jobs)
            limited_source_jobs = new_source_jobs[:max_new_jobs]
            if len(new_source_jobs) > len(limited_source_jobs):
                stopped_due_to_budget = True

            for source_job in limited_source_jobs:
                if deadline is not None and time.monotonic() >= deadline:
                    stopped_due_to_budget = True
                    remaining_unprocessed_new_jobs = len(limited_source_jobs) - new_jobs_processed + max(
                        0, len(new_source_jobs) - len(limited_source_jobs)
                    )
                    logger.info(
                        "source_ingestion_time_budget_reached",
                        source=source.source,
                        new_jobs_processed=new_jobs_processed,
                        remaining_unprocessed_new_jobs=remaining_unprocessed_new_jobs,
                    )
                    break
                try:
                    source_job = source.enrich_job(source_job)
                    new_jobs_processed += 1
                    if self._is_duplicate(db, source_job):
                        duplicates_skipped += 1
                        already_existing += 1
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
            db.rollback()
            jobs_created = 0
            run = IngestionRun(
                source=source.source,
                status="failed",
                error_summary=str(exc),
                jobs_created=jobs_created,
                jobs_skipped_duplicate=duplicates_skipped,
                jobs_failed=failures,
                finished_at=datetime.now(UTC),
            )
            db.add(run)
            db.flush()
            run_recorded_after_rollback = True
            logger.warning("source_ingestion_failed", source=source.source, error=str(exc))
        finally:
            if not run_recorded_after_rollback:
                run.jobs_created = jobs_created
                run.jobs_skipped_duplicate = duplicates_skipped
                run.jobs_failed = failures
                run.finished_at = datetime.now(UTC)
            logger.info(
                "source_ingestion_completed",
                source=source.source,
                jobs_found=jobs_found,
                already_existing=already_existing,
                new_jobs_processed=new_jobs_processed,
                jobs_created=jobs_created,
                duplicates_skipped=duplicates_skipped,
                failures=failures,
                remaining_unprocessed_new_jobs=remaining_unprocessed_new_jobs,
                stopped_due_to_budget=stopped_due_to_budget,
            )

        return SourceIngestionResult(
            source=source.source,
            jobs_found=jobs_found,
            jobs_created=jobs_created,
            duplicates_skipped=duplicates_skipped,
            failures=failures,
            errors=errors,
            already_existing=already_existing,
            new_jobs_processed=new_jobs_processed,
            remaining_unprocessed_new_jobs=remaining_unprocessed_new_jobs,
            stopped_due_to_budget=stopped_due_to_budget,
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


def _max_new_jobs_for_source(source: str) -> int:
    settings = get_settings()
    if source == "airswift":
        return max(0, settings.airswift_max_new_jobs_per_run)
    return 10_000


def _time_budget_for_source(source: str) -> float | None:
    settings = get_settings()
    if source == "airswift":
        return max(0.0, settings.airswift_time_budget_seconds)
    return None
