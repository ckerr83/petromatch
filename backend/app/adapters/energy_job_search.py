from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.adapters.base import SourceAdapter
from app.adapters.types import ExtractedJob
from app.core.config import get_settings
from app.core.enums import SourceName
from app.utils.text import parse_date_safe


class EnergyJobSearchAdapter(SourceAdapter):
    source_name = SourceName.ENERGYJOBSEARCH.value
    display_name = "Energy Job Search"
    base_url = get_settings().energyjobsearch_base_url

    def parse_html(self, html: str, limit: int = 50) -> list[ExtractedJob]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[ExtractedJob] = []

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                payload = json.loads(script.get_text(strip=True))
            except json.JSONDecodeError:
                continue
            payloads = payload if isinstance(payload, list) else [payload]
            for item in payloads:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") not in {"JobPosting", "Posting"}:
                    continue
                title = _string_or_none(item.get("title"))
                source_url = _string_or_none(item.get("url"))
                if not title or not source_url:
                    continue
                company = None
                hiring_org = item.get("hiringOrganization")
                if isinstance(hiring_org, dict):
                    company = _string_or_none(hiring_org.get("name"))
                jobs.append(
                    ExtractedJob(
                        source_name=self.source_name,
                        source_url=source_url,
                        external_job_id=_extract_external_id(source_url),
                        title=title,
                        company=company,
                        location=_extract_location(item.get("jobLocation")),
                        employment_type=_string_or_none(item.get("employmentType")),
                        posted_date=parse_date_safe(_string_or_none(item.get("datePosted"))),
                        raw_description=_string_or_none(item.get("description")),
                        source_payload=item,
                    )
                )
                if len(jobs) >= limit:
                    return jobs

        for card in soup.select("a[href*='/job/'], a[href*='/jobs/']"):
            href = card.get("href")
            title_text = card.get_text(" ", strip=True)
            if not href or not title_text:
                continue
            absolute_url = urljoin(self.base_url, href)
            if any(job.source_url == absolute_url for job in jobs):
                continue
            title = re.sub(r"\s+", " ", title_text).strip()
            if len(title) < 4:
                continue
            jobs.append(
                ExtractedJob(
                    source_name=self.source_name,
                    source_url=absolute_url,
                    external_job_id=_extract_external_id(absolute_url),
                    title=title,
                    source_payload={"extraction_method": "html_fallback"},
                )
            )
            if len(jobs) >= limit:
                break
        return jobs


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _extract_location(raw_location: object) -> str | None:
    if isinstance(raw_location, list):
        parts = [_extract_location(item) for item in raw_location]
        parts = [part for part in parts if part]
        return ", ".join(parts) if parts else None
    if isinstance(raw_location, dict):
        address = raw_location.get("address")
        if isinstance(address, dict):
            fields = [
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("addressCountry"),
            ]
            parts = [str(part).strip() for part in fields if isinstance(part, str) and part.strip()]
            return ", ".join(parts) if parts else None
    return None


def _extract_external_id(source_url: str) -> str | None:
    match = re.search(r"(\d{4,})", source_url)
    return match.group(1) if match else None

