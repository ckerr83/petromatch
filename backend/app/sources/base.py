from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceJob:
    source: str
    external_id: str
    title: str
    company: str
    location: str | None
    url: str
    description: str
    posted_date: date | None = None
    employment_type: str | None = None
    salary: str | None = None
    source_reference: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(ABC):
    source: str
    display_name: str

    @abstractmethod
    def fetch_jobs(self) -> list[SourceJob]:
        raise NotImplementedError

    def enrich_job(self, job: SourceJob) -> SourceJob:
        return job
