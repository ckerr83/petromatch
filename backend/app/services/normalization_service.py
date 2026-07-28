from __future__ import annotations

from dataclasses import asdict

from app.adapters.types import ExtractedJob
from app.core.enums import IndustrySubsection, OnshoreOffshore, Seniority
from app.utils.fingerprints import build_dedupe_fingerprint
from app.utils.text import normalize_text, normalize_whitespace, tokenize


class NormalizationService:
    def normalize_job_payload(self, job: ExtractedJob) -> dict:
        cleaned_description = normalize_whitespace(job.raw_description)
        return {
            "source_name": job.source_name,
            "source_url": job.source_url,
            "external_job_id": job.external_job_id,
            "title": normalize_text(job.title),
            "company": normalize_whitespace(job.company),
            "location": normalize_whitespace(job.location),
            "employment_type": normalize_whitespace(job.employment_type),
            "posted_date": job.posted_date,
            "raw_description": job.raw_description,
            "cleaned_description": cleaned_description,
            "recruiter_name": normalize_whitespace(job.recruiter_name),
            "source_payload": asdict(job)["source_payload"],
            "industry_subsections": self._classify_subsections(job.title, cleaned_description),
            "onshore_offshore": self._classify_onshore_offshore(job.title, cleaned_description),
            "seniority": self._classify_seniority(job.title, cleaned_description),
            "dedupe_fingerprint": build_dedupe_fingerprint(job.title, job.company, job.location),
        }

    def _classify_subsections(self, title: str | None, description: str | None) -> list[str]:
        text = " ".join([normalize_text(title), normalize_text(description)]).lower()
        mapping = {
            IndustrySubsection.PRODUCTION.value: ["production"],
            IndustrySubsection.OPERATIONS.value: ["operations", "operator"],
            IndustrySubsection.DRILLING.value: ["drilling", "driller"],
            IndustrySubsection.COMPLETIONS.value: ["completions"],
            IndustrySubsection.COMMISSIONING.value: ["commissioning"],
            IndustrySubsection.MAINTENANCE.value: ["maintenance", "mechanical technician"],
            IndustrySubsection.PROCESS.value: ["process", "process engineer"],
            IndustrySubsection.HSE.value: ["hse", "safety", "hsse"],
            IndustrySubsection.PROJECTS.value: ["project", "project engineer"],
            IndustrySubsection.INTEGRITY.value: ["integrity", "inspection", "asset integrity"],
            IndustrySubsection.SUBSEA.value: ["subsea"],
            IndustrySubsection.WELL_INTERVENTION.value: ["well intervention", "wireline", "slickline"],
            IndustrySubsection.CONSTRUCTION.value: ["construction"],
        }
        matches = [name for name, keywords in mapping.items() if any(keyword in text for keyword in keywords)]
        return matches or [IndustrySubsection.UNKNOWN.value]

    def _classify_onshore_offshore(self, title: str | None, description: str | None) -> str:
        text = " ".join([normalize_text(title), normalize_text(description)]).lower()
        has_onshore = "onshore" in text
        has_offshore = "offshore" in text
        if has_onshore and has_offshore:
            return OnshoreOffshore.HYBRID.value
        if has_offshore:
            return OnshoreOffshore.OFFSHORE.value
        if has_onshore:
            return OnshoreOffshore.ONSHORE.value
        return OnshoreOffshore.UNKNOWN.value

    def _classify_seniority(self, title: str | None, description: str | None) -> str:
        text = " ".join([normalize_text(title), normalize_text(description)]).lower()
        if any(token in text for token in ("chief", "vp", "director", "executive")):
            return Seniority.EXECUTIVE.value
        if any(token in text for token in ("manager", "superintendent")):
            return Seniority.SUPERINTENDENT_MANAGER.value
        if any(token in text for token in ("lead", "principal")):
            return Seniority.LEAD.value
        if any(token in text for token in ("senior", "sr.")):
            return Seniority.SENIOR.value
        if any(token in text for token in ("junior", "graduate", "entry")):
            return Seniority.ENTRY.value
        if tokenize(text):
            return Seniority.MID.value
        return Seniority.UNKNOWN.value

