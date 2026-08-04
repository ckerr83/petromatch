from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import cron, emails, extraction, health, ingestion, jobs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(cron.router, prefix="/cron", tags=["cron"])
api_router.include_router(emails.router, prefix="/emails", tags=["emails"])
api_router.include_router(extraction.router, prefix="/extraction", tags=["extraction"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
