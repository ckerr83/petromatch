from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_db
from app.db.models import Job
from app.schemas.job import JobListResponse, JobResponse

router = APIRouter()


@router.get("", response_model=JobListResponse)
def list_jobs(
    source: str | None = Query(default=None),
    location: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> JobListResponse:
    query = select(Job).order_by(Job.received_date.desc(), Job.id.desc())
    if source:
        query = query.where(Job.source == source)
    if location:
        query = query.where(Job.location.ilike(f"%{location}%"))
    if keyword:
        query = query.where(
            or_(
                Job.job_title.ilike(f"%{keyword}%"),
                Job.company.ilike(f"%{keyword}%"),
                Job.raw_text.ilike(f"%{keyword}%"),
            )
        )
    jobs = db.scalars(query).all()
    items = [JobResponse.model_validate(job) for job in jobs]
    return JobListResponse(total=len(items), items=items)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobResponse:
    job = db.scalar(select(Job).where(Job.id == job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobResponse.model_validate(job)
