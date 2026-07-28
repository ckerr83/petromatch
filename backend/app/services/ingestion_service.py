from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import IngestionRunStatus
from app.core.logging import get_logger
from app.db.models import IngestionRun, Job
from app.services.normalization_service import NormalizationService
from app.services.source_registry import SourceRegistry

logger = get_logger(__name__)


class IngestionService:
    def __init__(self) -> None:
        self.registry = SourceRegistry()
        self.normalizer = NormalizationService()

    async def ingest_source(
        self,
        db: Session,
        source_name: str,
        raw_html: str | None = None,
        limit: int = 50,
    ) -> IngestionRun:
        adapter = self.registry.get(source_name)
        run = IngestionRun(source_name=source_name, status=IngestionRunStatus.STARTED.value)
        db.add(run)
        db.flush()

        jobs_created = 0
        jobs_updated = 0
        jobs_failed = 0

        try:
            extracted_jobs = await adapter.extract(raw_html=raw_html, limit=limit)
            run.jobs_seen = len(extracted_jobs)

            for extracted_job in extracted_jobs:
                if not extracted_job.title or not extracted_job.source_url:
                    jobs_failed += 1
                    continue
                normalized = self.normalizer.normalize_job_payload(extracted_job)
                was_existing, _job = self._upsert_job(db, normalized)
                if was_existing:
                    jobs_updated += 1
                else:
                    jobs_created += 1

            run.status = IngestionRunStatus.SUCCEEDED.value if jobs_failed == 0 else IngestionRunStatus.PARTIAL.value
        except Exception as exc:
            logger.exception("source_ingestion_failed", source_name=source_name, error=str(exc))
            run.status = IngestionRunStatus.FAILED.value
            run.error_summary = str(exc)

        run.jobs_created = jobs_created
        run.jobs_updated = jobs_updated
        run.jobs_failed = jobs_failed
        run.finished_at = datetime.now(timezone.utc)
        db.flush()
        return run

    async def ingest_all(self, db: Session, limit: int = 50) -> list[IngestionRun]:
        results: list[IngestionRun] = []
        for adapter in self.registry.all():
            results.append(await self.ingest_source(db, adapter.source_name, limit=limit))
        return results

    def _upsert_job(self, db: Session, normalized: dict) -> tuple[bool, Job]:
        existing = db.scalar(select(Job).where(Job.source_url == normalized["source_url"]).limit(1))
        if existing is None and normalized.get("external_job_id"):
            existing = db.scalar(
                select(Job)
                .where(Job.source_name == normalized["source_name"])
                .where(Job.external_job_id == normalized["external_job_id"])
                .limit(1)
            )

        if existing is None:
            job = Job(**normalized)
            db.add(job)
            db.flush()
            return (False, job)

        for field, value in normalized.items():
            setattr(existing, field, value)
        existing.ingested_at = datetime.now(timezone.utc)
        db.flush()
        return (True, existing)

