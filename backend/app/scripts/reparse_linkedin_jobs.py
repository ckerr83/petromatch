from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import select

from app.db.models import Job
from app.db.session import SessionLocal
from app.services.parsers.linkedin import infer_linkedin_fields_from_text


@dataclass(frozen=True)
class JobUpdatePreview:
    job_id: int
    old_title: str | None
    new_title: str | None
    old_company: str | None
    new_company: str | None
    old_location: str | None
    new_location: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Reparse existing LinkedIn jobs from stored raw_text.")
    parser.add_argument("--apply", action="store_true", help="Persist updates. Defaults to dry-run.")
    args = parser.parse_args()

    updates = reparse_linkedin_jobs(apply=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"{mode}: {len(updates)} LinkedIn job(s) would be updated.")
    for update in updates:
        print(
            f"job_id={update.job_id} "
            f"title={update.old_title!r}->{update.new_title!r} "
            f"company={update.old_company!r}->{update.new_company!r} "
            f"location={update.old_location!r}->{update.new_location!r}"
        )


def reparse_linkedin_jobs(*, apply: bool) -> list[JobUpdatePreview]:
    updates: list[JobUpdatePreview] = []
    with SessionLocal() as db:
        jobs = db.scalars(select(Job).where(Job.source == "linkedin").order_by(Job.id.asc())).all()
        for job in jobs:
            title, company, location = infer_linkedin_fields_from_text(job.raw_text)
            if not any((title, company, location)):
                continue
            if (job.job_title, job.company, job.location) == (title, company, location):
                continue

            updates.append(
                JobUpdatePreview(
                    job_id=job.id,
                    old_title=job.job_title,
                    new_title=title,
                    old_company=job.company,
                    new_company=company,
                    old_location=job.location,
                    new_location=location,
                )
            )
            if apply:
                job.job_title = title
                job.company = company
                job.location = location

        if apply:
            db.commit()

    return updates


if __name__ == "__main__":
    main()
