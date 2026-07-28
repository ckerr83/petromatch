from __future__ import annotations

from enum import Enum


class SourceName(str, Enum):
    ENERGYJOBSEARCH = "energyjobsearch"
    RIGZONE = "rigzone"


class IndustrySubsection(str, Enum):
    PRODUCTION = "production"
    OPERATIONS = "operations"
    DRILLING = "drilling"
    COMPLETIONS = "completions"
    COMMISSIONING = "commissioning"
    MAINTENANCE = "maintenance"
    PROCESS = "process"
    HSE = "hse"
    PROJECTS = "projects"
    INTEGRITY = "integrity"
    SUBSEA = "subsea"
    WELL_INTERVENTION = "well_intervention"
    CONSTRUCTION = "construction"
    UNKNOWN = "unknown"


class OnshoreOffshore(str, Enum):
    ONSHORE = "onshore"
    OFFSHORE = "offshore"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class Seniority(str, Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    SUPERINTENDENT_MANAGER = "superintendent_manager"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class WorkflowStatus(str, Enum):
    NEW = "new"
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    DISMISSED = "dismissed"


class IngestionRunStatus(str, Enum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class RecommendationLabel(str, Enum):
    STRONG_MATCH = "strong_match"
    POSSIBLE_MATCH = "possible_match"
    WEAK_MATCH = "weak_match"

