from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    overall_score: int
    title_fit_score: int
    industry_fit_score: int
    location_fit_score: int
    onshore_offshore_fit_score: int
    seniority_fit_score: int
    recommendation_label: str
    explanation: str
    matched_reasons: list[str]
    missing_points: list[str]
    scored_at: datetime | None = None

