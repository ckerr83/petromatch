from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Job, ProcessedEmail
from app.services.daily_ingestion_service import DailyIngestionService
from app.services.extraction_service import ExtractionService
from app.services.gmail_ingestion_service import GmailIngestionResult
from app.services.source_ingestion_service import SourceIngestionService
from app.sources.airswift import AirswiftSource, parse_detail_page, parse_listing_page
from app.sources.base import SourceAdapter, SourceJob


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return session_factory()


def test_parse_airswift_listing() -> None:
    jobs = parse_listing_page(LISTING_PAGE_1)

    assert len(jobs) == 1
    assert jobs[0].source == "airswift"
    assert jobs[0].external_id == "1278092"
    assert jobs[0].title == "Senior Subsea Structural Engineer"
    assert jobs[0].company == "Airswift"
    assert jobs[0].location == "Kuala Lumpur, Malaysia"
    assert jobs[0].employment_type == "Permanent"
    assert jobs[0].posted_date is not None


def test_parse_airswift_detail_prefers_jobposting_and_reference() -> None:
    job = parse_detail_page(DETAIL_PAGE, "https://www.airswift.com/jobs/senior-subsea-structural-engineer-1278092")

    assert job is not None
    assert job.external_id == "1278092"
    assert job.source_reference == "1278092"
    assert job.description.startswith("About The Job")
    assert job.posted_date is not None
    assert job.employment_type == "Permanent"
    assert job.raw_metadata["detail_stats"]["Sector"] == "Energy - Oil & Gas"


def test_airswift_pagination_fetches_all_pages() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if str(request.url).endswith("page_num=2"):
            return httpx.Response(200, text=LISTING_PAGE_2)
        if request.url.path == "/jobs/detail-1278092":
            return httpx.Response(200, text=DETAIL_PAGE)
        if request.url.path == "/jobs/detail-1278093":
            return httpx.Response(200, text=DETAIL_PAGE_2)
        return httpx.Response(200, text=LISTING_PAGE_1)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://www.airswift.com")
    jobs = AirswiftSource(http_client=client).fetch_jobs()

    assert len(jobs) == 2
    assert any("page_num=2" in url for url in requested)


def test_duplicate_external_ids_are_stored_once() -> None:
    db = _session()
    source = StaticSource(
        [
            _source_job("1278092", "https://www.airswift.com/jobs/detail-1278092"),
            _source_job("1278092", "https://www.airswift.com/jobs/detail-1278092"),
        ]
    )

    result = SourceIngestionService(sources=[source]).run_source(db, source)

    assert result.jobs_found == 2
    assert result.jobs_created == 1
    assert result.duplicates_skipped == 1
    assert len(db.scalars(select(Job)).all()) == 1


def test_no_jobs_returned_succeeds() -> None:
    db = _session()
    source = StaticSource([])

    result = SourceIngestionService(sources=[source]).run_source(db, source)

    assert result.jobs_found == 0
    assert result.jobs_created == 0
    assert result.errors == []


def test_remote_http_failure_is_reported() -> None:
    db = _session()
    source = FailingSource()

    result = SourceIngestionService(sources=[source]).run_source(db, source)

    assert result.jobs_created == 0
    assert result.failures == 1
    assert "RuntimeError" in result.errors[0]


def test_repeated_daily_execution_does_not_duplicate_source_jobs() -> None:
    db = _session()
    service = DailyIngestionService(
        gmail_ingestion_service=EmptyGmailIngestionService(),
        extraction_service=ExtractionService(),
        source_ingestion_service=SourceIngestionService(
            sources=[StaticSource([_source_job("1278092", "https://www.airswift.com/jobs/detail-1278092")])]
        ),
    )

    first = service.run_once(db)
    db.commit()
    second = service.run_once(db)
    db.commit()

    assert first.sources["airswift"]["jobs_created"] == 1
    assert second.sources["airswift"]["jobs_created"] == 0
    assert second.sources["airswift"]["duplicates_skipped"] == 1
    assert len(db.scalars(select(Job)).all()) == 1


def test_gmail_still_succeeds_if_airswift_fails() -> None:
    db = _session()
    email = ProcessedEmail(
        gmail_message_id="gmail-1",
        source="gmail",
        sender="jobs-listings@linkedin.com",
        recipients=["candidate@example.com"],
        subject="LinkedIn job alert",
        received_date=datetime(2026, 8, 5, 10, 0, tzinfo=UTC),
        raw_html_body='<a href="https://www.linkedin.com/jobs/view/1234567890/">Senior Engineer</a><span>PetroCo · Houston, TX</span>',
        status="ingested",
        extraction_status="pending",
    )
    db.add(email)
    db.commit()
    service = DailyIngestionService(
        gmail_ingestion_service=EmptyGmailIngestionService(),
        extraction_service=ExtractionService(),
        source_ingestion_service=SourceIngestionService(sources=[FailingSource()]),
    )

    result = service.run_once(db)

    assert result.gmail["jobs_created"] == 1
    assert result.jobs_created == 1
    assert result.errors


def test_airswift_initial_backlog_larger_than_batch_limit_processes_only_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_airswift_budget(monkeypatch, max_new_jobs=2)
    db = _session()
    source = CountingSource(
        [
            _source_job("1", "https://www.airswift.com/jobs/detail-1"),
            _source_job("2", "https://www.airswift.com/jobs/detail-2"),
            _source_job("3", "https://www.airswift.com/jobs/detail-3"),
        ]
    )

    result = SourceIngestionService(sources=[source]).run_source(db, source)

    assert result.jobs_found == 3
    assert result.new_jobs_processed == 2
    assert result.jobs_created == 2
    assert result.remaining_unprocessed_new_jobs == 1
    assert result.stopped_due_to_budget is True
    assert source.enriched_external_ids == ["1", "2"]


def test_airswift_second_run_continues_remaining_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_airswift_budget(monkeypatch, max_new_jobs=2)
    db = _session()
    source = CountingSource(
        [
            _source_job("1", "https://www.airswift.com/jobs/detail-1"),
            _source_job("2", "https://www.airswift.com/jobs/detail-2"),
            _source_job("3", "https://www.airswift.com/jobs/detail-3"),
        ]
    )
    service = SourceIngestionService(sources=[source])

    first = service.run_source(db, source)
    db.commit()
    source.enriched_external_ids.clear()
    second = service.run_source(db, source)
    db.commit()

    assert first.jobs_created == 2
    assert second.already_existing == 2
    assert second.new_jobs_processed == 1
    assert second.jobs_created == 1
    assert second.remaining_unprocessed_new_jobs == 0
    assert source.enriched_external_ids == ["3"]
    assert len(db.scalars(select(Job)).all()) == 3


def test_existing_airswift_jobs_do_not_trigger_detail_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_airswift_budget(monkeypatch, max_new_jobs=10)
    db = _session()
    existing = _job_from_source_for_test(_source_job("1", "https://www.airswift.com/jobs/detail-1"))
    db.add(existing)
    db.commit()
    source = CountingSource([_source_job("1", "https://www.airswift.com/jobs/detail-1")])

    result = SourceIngestionService(sources=[source]).run_source(db, source)

    assert result.already_existing == 1
    assert result.new_jobs_processed == 0
    assert result.jobs_created == 0
    assert source.enriched_external_ids == []


def test_airswift_detail_failure_does_not_abort_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_airswift_budget(monkeypatch, max_new_jobs=10)
    db = _session()
    source = CountingSource(
        [
            _source_job("1", "https://www.airswift.com/jobs/detail-1"),
            _source_job("2", "https://www.airswift.com/jobs/detail-2"),
        ],
        failing_external_ids={"1"},
    )

    result = SourceIngestionService(sources=[source]).run_source(db, source)

    assert result.failures == 1
    assert result.jobs_created == 1
    assert result.errors
    assert len(db.scalars(select(Job)).all()) == 1


def test_daily_execution_with_airswift_batch_limit_keeps_gmail_working(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_airswift_budget(monkeypatch, max_new_jobs=1)
    db = _session()
    email = ProcessedEmail(
        gmail_message_id="gmail-1",
        source="gmail",
        sender="jobs-listings@linkedin.com",
        recipients=["candidate@example.com"],
        subject="LinkedIn job alert",
        received_date=datetime(2026, 8, 5, 10, 0, tzinfo=UTC),
        raw_html_body='<a href="https://www.linkedin.com/jobs/view/1234567890/">Senior Engineer</a><span>PetroCo · Houston, TX</span>',
        status="ingested",
        extraction_status="pending",
    )
    db.add(email)
    db.commit()
    source = CountingSource(
        [
            _source_job("1", "https://www.airswift.com/jobs/detail-1"),
            _source_job("2", "https://www.airswift.com/jobs/detail-2"),
        ]
    )
    service = DailyIngestionService(
        gmail_ingestion_service=EmptyGmailIngestionService(),
        extraction_service=ExtractionService(),
        source_ingestion_service=SourceIngestionService(sources=[source]),
    )

    result = service.run_once(db)

    assert result.gmail["jobs_created"] == 1
    assert result.airswift["new_jobs_processed"] == 1
    assert result.airswift["remaining_unprocessed_new_jobs"] == 1
    assert result.jobs_created == 2


def test_airswift_repeated_runs_remain_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_airswift_budget(monkeypatch, max_new_jobs=10)
    db = _session()
    source = CountingSource([_source_job("1", "https://www.airswift.com/jobs/detail-1")])
    service = SourceIngestionService(sources=[source])

    first = service.run_source(db, source)
    db.commit()
    second = service.run_source(db, source)
    db.commit()

    assert first.jobs_created == 1
    assert second.jobs_created == 0
    assert second.already_existing == 1
    assert second.new_jobs_processed == 0
    assert len(db.scalars(select(Job)).all()) == 1


class StaticSource(SourceAdapter):
    source = "airswift"
    display_name = "Airswift"

    def __init__(self, jobs: list[SourceJob]) -> None:
        self.jobs = jobs

    def fetch_jobs(self) -> list[SourceJob]:
        return self.jobs


class FailingSource(SourceAdapter):
    source = "airswift"
    display_name = "Airswift"

    def fetch_jobs(self) -> list[SourceJob]:
        raise RuntimeError("remote unavailable")


class EmptyGmailIngestionService:
    def run_once(self, db: Session) -> GmailIngestionResult:
        return GmailIngestionResult(
            emails_discovered=0,
            new_emails_stored=0,
            duplicates_skipped=0,
            failures=0,
            errors=[],
        )


class CountingSource(SourceAdapter):
    source = "airswift"
    display_name = "Airswift"

    def __init__(self, jobs: list[SourceJob], failing_external_ids: set[str] | None = None) -> None:
        self.jobs = jobs
        self.failing_external_ids = failing_external_ids or set()
        self.enriched_external_ids: list[str] = []

    def fetch_jobs(self) -> list[SourceJob]:
        return self.jobs

    def enrich_job(self, job: SourceJob) -> SourceJob:
        self.enriched_external_ids.append(job.external_id)
        if job.external_id in self.failing_external_ids:
            raise RuntimeError("detail unavailable")
        return job


def _source_job(external_id: str, url: str) -> SourceJob:
    return SourceJob(
        source="airswift",
        external_id=external_id,
        title=f"Senior Subsea Structural Engineer {external_id}",
        company="Airswift",
        location="Kuala Lumpur, Malaysia",
        url=url,
        description=f"About The Job Responsibilities of Role {external_id}.",
        source_reference=external_id,
    )


def _job_from_source_for_test(source_job: SourceJob) -> Job:
    return Job(
        processed_email_id=None,
        source=source_job.source,
        external_id=source_job.external_id,
        job_url=source_job.url,
        dedupe_fingerprint=None,
        job_title=source_job.title,
        company=source_job.company,
        location=source_job.location,
        posted_date=source_job.posted_date,
        received_date=datetime.now(UTC),
        raw_text=source_job.description,
        source_payload={},
    )


def _configure_airswift_budget(monkeypatch: pytest.MonkeyPatch, *, max_new_jobs: int) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("AIRSWIFT_MAX_NEW_JOBS_PER_RUN", str(max_new_jobs))
    monkeypatch.setenv("AIRSWIFT_TIME_BUDGET_SECONDS", "170")
    get_settings.cache_clear()


LISTING_PAGE_1 = """
<p class="c-card-job-header__summary">Found 2 jobs on 2 pages</p>
<article class="c-card-job-item">
  <div class="c-card-job-item__top">
    <p class="c-card-job-item__top-cell"><img alt="Employment Type">Permanent</p>
    <p class="c-card-job-item__top-cell"><img alt="Date Published">5 Aug 2026</p>
  </div>
  <p class="c-card-job-item__location"><img alt="Location">Kuala Lumpur, Malaysia</p>
  <p class="c-card-job-item__title"><a href="/jobs/detail-1278092">Senior Subsea Structural Engineer</a></p>
  <p class="c-card-job-item__summary">About The Job Responsibilities of Role...</p>
</article>
"""

LISTING_PAGE_2 = """
<p class="c-card-job-header__summary">Found 2 jobs on 2 pages</p>
<article class="c-card-job-item">
  <div class="c-card-job-item__top">
    <p class="c-card-job-item__top-cell"><img alt="Employment Type">Contract</p>
    <p class="c-card-job-item__top-cell"><img alt="Date Published">4 Aug 2026</p>
  </div>
  <p class="c-card-job-item__location"><img alt="Location">Doha, Qatar</p>
  <p class="c-card-job-item__title"><a href="/jobs/detail-1278093">Project Safety Officer</a></p>
  <p class="c-card-job-item__summary">Airswift are hiring...</p>
</article>
"""

DETAIL_PAGE = """
<link rel="canonical" href="https://www.airswift.com/jobs/detail-1278092">
<h1 class="c-jobs-article-header__title">Senior Subsea Structural Engineer</h1>
<p class="c-jobs-article-header__location">Kuala Lumpur, Malaysia</p>
<div class="c-jobs-article-stats__content"><strong>Job reference</strong>1278092</div>
<div class="c-jobs-article-stats__content"><strong>Location</strong>Kuala Lumpur, Malaysia</div>
<div class="c-jobs-article-stats__content"><strong>Sector</strong>Energy - Oil &amp; Gas</div>
<div class="c-jobs-article-stats__content"><strong>Employment type</strong>Permanent</div>
<div class="c-jobs-article-stats__content"><strong>Date published</strong>August 4, 2026</div>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "JobPosting",
  "title": "Senior Subsea Structural Engineer",
  "description": "About The Job Responsibilities of Role.",
  "datePosted": "2026-08-04",
  "employmentType": "Permanent",
  "jobLocation": {"@type": "Place", "address": {"addressLocality": "Kuala Lumpur", "addressCountry": "Malaysia"}}
}
</script>
"""

DETAIL_PAGE_2 = DETAIL_PAGE.replace("1278092", "1278093").replace(
    "Senior Subsea Structural Engineer", "Project Safety Officer"
)
