from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Job, ProcessedEmail
from app.services.parsers import EmailParseContext, ParsedOpportunity, ParserRegistry
from app.services.parsers.utils import normalize_job_url
from app.utils.fingerprints import build_dedupe_fingerprint
from app.utils.text import normalize_whitespace

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExtractionResult:
    emails_processed: int
    emails_parsed: int
    emails_partially_parsed: int
    emails_failed: int
    emails_with_no_jobs: int
    jobs_found: int
    jobs_created: int
    duplicates_skipped: int
    errors: list[str]


@dataclass(frozen=True)
class EmailExtractionResult:
    email_id: int
    parser: str | None
    extraction_status: str
    jobs_found: int
    jobs_created: int
    duplicates_skipped: int
    failures: int
    errors: list[str]


class ExtractionService:
    def __init__(self, parser_registry: ParserRegistry | None = None) -> None:
        self.parser_registry = parser_registry or ParserRegistry()

    def run_pending(self, db: Session) -> ExtractionResult:
        emails = db.scalars(
            select(ProcessedEmail)
            .where(ProcessedEmail.status == "ingested")
            .where(ProcessedEmail.extraction_status == "pending")
            .order_by(ProcessedEmail.received_date.asc().nullsfirst(), ProcessedEmail.id.asc())
        ).all()

        logger.info("extraction_started", pending_emails=len(emails))
        results = [self.extract_email(db, email, reset_existing=False) for email in emails]
        errors = [error for result in results for error in result.errors]
        logger.info(
            "extraction_completed",
            emails_processed=len(results),
            jobs_found=sum(result.jobs_found for result in results),
            jobs_created=sum(result.jobs_created for result in results),
            duplicates_skipped=sum(result.duplicates_skipped for result in results),
            errors=len(errors),
        )
        return ExtractionResult(
            emails_processed=len(results),
            emails_parsed=sum(1 for result in results if result.extraction_status == "parsed"),
            emails_partially_parsed=sum(1 for result in results if result.extraction_status == "partially_parsed"),
            emails_failed=sum(1 for result in results if result.extraction_status == "failed"),
            emails_with_no_jobs=sum(1 for result in results if result.extraction_status == "no_jobs_found"),
            jobs_found=sum(result.jobs_found for result in results),
            jobs_created=sum(result.jobs_created for result in results),
            duplicates_skipped=sum(result.duplicates_skipped for result in results),
            errors=errors,
        )

    def extract_email_by_id(self, db: Session, email_id: int) -> EmailExtractionResult | None:
        email = db.get(ProcessedEmail, email_id)
        if email is None:
            return None
        return self.extract_email(db, email, reset_existing=True)

    def extract_email(
        self,
        db: Session,
        email: ProcessedEmail,
        *,
        reset_existing: bool,
    ) -> EmailExtractionResult:
        if reset_existing:
            db.execute(delete(Job).where(Job.processed_email_id == email.id))
            db.flush()

        context = EmailParseContext(
            sender=email.sender,
            subject=email.subject,
            html_body=email.raw_html_body,
            plain_text_body=email.plain_text_body,
        )
        parser = self.parser_registry.select_parser(context)
        parser_name = parser.source if parser else None
        jobs_found = 0
        jobs_created = 0
        duplicates_skipped = 0
        failures = 0
        errors: list[str] = []

        try:
            if parser is None:
                email.extraction_status = "failed"
                email.parsing_error = "No parser available for email content."
                errors.append(email.parsing_error)
                logger.warning("email_extraction_failed", email_id=email.id, error=email.parsing_error)
                return EmailExtractionResult(email.id, None, "failed", 0, 0, 0, 1, errors)

            opportunities = parser.parse(context)
            jobs_found = len(opportunities)
            if not opportunities:
                email.extraction_status = "no_jobs_found"
                email.jobs_extracted_count = 0
                email.parsing_error = None
                email.parsed_at = datetime.now(UTC)
                return EmailExtractionResult(email.id, parser_name, "no_jobs_found", 0, 0, 0, 0, errors)

            for opportunity in opportunities:
                try:
                    job = self._job_from_opportunity(email, opportunity)
                    if self._is_duplicate(db, job):
                        duplicates_skipped += 1
                        continue
                    with db.begin_nested():
                        db.add(job)
                        db.flush()
                    jobs_created += 1
                except Exception as exc:  # noqa: BLE001
                    failures += 1
                    error = f"email_id={email.id}: {type(exc).__name__}: {exc}"
                    errors.append(error)
                    logger.warning("job_extraction_failed", email_id=email.id, error=str(exc))

            email.jobs_extracted_count = jobs_created
            email.parsed_at = datetime.now(UTC)
            email.parsing_error = f"{failures} job(s) failed during extraction." if failures else None
            email.extraction_status = "partially_parsed" if failures else "parsed"
            db.add(email)
            db.flush()
            return EmailExtractionResult(
                email_id=email.id,
                parser=parser_name,
                extraction_status=email.extraction_status,
                jobs_found=jobs_found,
                jobs_created=jobs_created,
                duplicates_skipped=duplicates_skipped,
                failures=failures,
                errors=errors,
            )
        except Exception as exc:  # noqa: BLE001
            error = f"email_id={email.id}: {type(exc).__name__}: {exc}"
            errors.append(error)
            email_id = email.id
            if not db.is_active:
                db.rollback()
                email = db.get(ProcessedEmail, email_id) or email
            email.extraction_status = "failed"
            email.parsing_error = str(exc)
            email.parsed_at = datetime.now(UTC)
            email.jobs_extracted_count = jobs_created
            db.add(email)
            db.flush()
            return EmailExtractionResult(
                email_id=email.id,
                parser=parser_name,
                extraction_status="failed",
                jobs_found=jobs_found,
                jobs_created=jobs_created,
                duplicates_skipped=duplicates_skipped,
                failures=failures + 1,
                errors=errors,
            )

    def _job_from_opportunity(self, email: ProcessedEmail, opportunity: ParsedOpportunity) -> Job:
        if email.received_date is None:
            raise ValueError("Email has no received_date; cannot create job received_date.")

        job_title = normalize_whitespace(opportunity.job_title)
        company = normalize_whitespace(opportunity.company)
        location = normalize_whitespace(opportunity.location)
        job_url = normalize_job_url(opportunity.job_url)
        fingerprint = _conservative_fingerprint(job_title, company, location)

        return Job(
            processed_email_id=email.id,
            source=opportunity.source,
            external_id=normalize_whitespace(opportunity.external_id),
            job_url=job_url,
            dedupe_fingerprint=fingerprint,
            job_title=job_title,
            company=company,
            location=location,
            posted_date=opportunity.posted_date,
            received_date=email.received_date,
            raw_text=opportunity.raw_text,
            source_payload={"parser": opportunity.source},
        )

    def _is_duplicate(self, db: Session, job: Job) -> bool:
        checks = []
        if job.job_url:
            checks.append(Job.job_url == job.job_url)
        if job.external_id:
            checks.append((Job.source == job.source) & (Job.external_id == job.external_id))
        if job.dedupe_fingerprint:
            checks.append(Job.dedupe_fingerprint == job.dedupe_fingerprint)
        if not checks:
            return False
        return db.scalar(select(Job.id).where(or_(*checks)).limit(1)) is not None


def _conservative_fingerprint(title: str | None, company: str | None, location: str | None) -> str | None:
    if not title or not (company or location):
        return None
    return build_dedupe_fingerprint(title, company, location)
