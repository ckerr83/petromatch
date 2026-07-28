from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import RecommendationLabel
from app.db.models import Job, JobScore, Profile
from app.utils.similarity import similarity
from app.utils.text import normalize_text


@dataclass(slots=True)
class ScoreResult:
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


class ScoringService:
    def score_job(self, job: Job, profile: Profile) -> ScoreResult:
        matched_reasons: list[str] = []
        missing_points: list[str] = []

        title_fit = self._score_title(job, profile, matched_reasons, missing_points)
        industry_fit = self._score_industry(job, profile, matched_reasons, missing_points)
        location_fit = self._score_location(job, profile, matched_reasons, missing_points)
        onoff_fit = self._score_onshore_offshore(job, profile, matched_reasons, missing_points)
        seniority_fit = self._score_seniority(job, profile, matched_reasons, missing_points)

        blocker_penalty = self._blocker_penalty(job, profile, matched_reasons, missing_points)
        overall = round(
            (title_fit * 0.35)
            + (industry_fit * 0.2)
            + (location_fit * 0.2)
            + (onoff_fit * 0.1)
            + (seniority_fit * 0.15)
        )
        overall = max(0, min(100, overall - blocker_penalty))
        recommendation = self._label_for_score(overall)
        explanation = self._build_explanation(overall, matched_reasons, missing_points)
        return ScoreResult(
            overall_score=overall,
            title_fit_score=title_fit,
            industry_fit_score=industry_fit,
            location_fit_score=location_fit,
            onshore_offshore_fit_score=onoff_fit,
            seniority_fit_score=seniority_fit,
            recommendation_label=recommendation,
            explanation=explanation,
            matched_reasons=matched_reasons,
            missing_points=missing_points,
        )

    def persist_score(self, db: Session, job: Job, profile: Profile, result: ScoreResult) -> JobScore:
        score = db.scalar(
            select(JobScore).where(JobScore.job_id == job.id).where(JobScore.profile_id == profile.id).limit(1)
        )
        payload = result.__dict__.copy()
        if score is None:
            score = JobScore(job_id=job.id, profile_id=profile.id, **payload)
            db.add(score)
        else:
            for field, value in payload.items():
                setattr(score, field, value)
            score.scored_at = datetime.now(timezone.utc)
        job.cv_version_used = profile.profile_version
        db.flush()
        db.refresh(score)
        return score

    def score_and_persist(self, db: Session, job: Job, profile: Profile) -> JobScore:
        result = self.score_job(job, profile)
        return self.persist_score(db, job, profile, result)

    def _score_title(self, job: Job, profile: Profile, matched: list[str], missing: list[str]) -> int:
        if not profile.target_job_titles:
            missing.append("No target job titles configured in profile.")
            return 50
        best = max(similarity(job.title, target) for target in profile.target_job_titles)
        if best >= 0.85:
            matched.append("Job title closely matches target titles.")
            return 100
        if best >= 0.6:
            matched.append("Job title partially matches target titles.")
            return 70
        missing.append("Job title does not closely match target titles.")
        return 25

    def _score_industry(self, job: Job, profile: Profile, matched: list[str], missing: list[str]) -> int:
        if not profile.preferred_industry_subsections:
            missing.append("No preferred industry subsections configured.")
            return 50
        overlap = set(job.industry_subsections).intersection(profile.preferred_industry_subsections)
        if overlap:
            matched.append(f"Industry subsection overlap: {', '.join(sorted(overlap))}.")
            return 100
        missing.append("No industry subsection overlap found.")
        return 20

    def _score_location(self, job: Job, profile: Profile, matched: list[str], missing: list[str]) -> int:
        if not profile.target_locations:
            missing.append("No target locations configured.")
            return 50
        job_location = normalize_text(job.location).lower()
        if any(normalize_text(location).lower() in job_location for location in profile.target_locations if location):
            matched.append("Job location matches target locations.")
            return 100
        if not job_location:
            missing.append("Job location is unclear.")
            return 40
        missing.append("Job location is outside target locations.")
        return 20

    def _score_onshore_offshore(self, job: Job, profile: Profile, matched: list[str], missing: list[str]) -> int:
        if not profile.preferred_onshore_offshore:
            missing.append("No onshore/offshore preference configured.")
            return 50
        if job.onshore_offshore in profile.preferred_onshore_offshore:
            matched.append("Onshore/offshore classification matches profile preference.")
            return 100
        if job.onshore_offshore == "unknown":
            missing.append("Onshore/offshore classification is unclear.")
            return 40
        missing.append("Onshore/offshore classification does not match preference.")
        return 10

    def _score_seniority(self, job: Job, profile: Profile, matched: list[str], missing: list[str]) -> int:
        if profile.years_of_experience is None:
            missing.append("Years of experience not set in profile.")
            return 50
        years = profile.years_of_experience
        expected = "entry" if years < 3 else "mid" if years < 7 else "senior" if years < 12 else "lead"
        if job.seniority == expected:
            matched.append("Seniority aligns with profile experience.")
            return 100
        if job.seniority in {"unknown", "mid"} and expected in {"mid", "senior"}:
            matched.append("Seniority is broadly compatible.")
            return 65
        missing.append("Seniority appears misaligned.")
        return 20

    def _blocker_penalty(self, job: Job, profile: Profile, matched: list[str], missing: list[str]) -> int:
        haystack = " ".join(
            [
                normalize_text(job.title),
                normalize_text(job.cleaned_description),
                normalize_text(job.location),
            ]
        ).lower()
        penalty = 0
        for blocker in profile.hard_blockers:
            if normalize_text(blocker).lower() in haystack:
                missing.append(f"Hard blocker matched: {blocker}.")
                penalty += 25
        for keyword in profile.exclude_keywords:
            if normalize_text(keyword).lower() in haystack:
                missing.append(f"Excluded keyword found: {keyword}.")
                penalty += 10
        for keyword in profile.include_keywords:
            if normalize_text(keyword).lower() in haystack:
                matched.append(f"Included keyword matched: {keyword}.")
        return penalty

    def _label_for_score(self, score: int) -> str:
        if score >= 80:
            return RecommendationLabel.STRONG_MATCH.value
        if score >= 55:
            return RecommendationLabel.POSSIBLE_MATCH.value
        return RecommendationLabel.WEAK_MATCH.value

    def _build_explanation(self, score: int, matched: list[str], missing: list[str]) -> str:
        if matched:
            return f"Score {score}/100 based on {matched[0].rstrip('.')}."
        if missing:
            return f"Score {score}/100 with main uncertainty: {missing[0].rstrip('.')}."
        return f"Score {score}/100."
