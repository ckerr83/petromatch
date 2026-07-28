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


class RigzoneAdapter(SourceAdapter):
    source_name = SourceName.RIGZONE.value
    display_name = "Rigzone"
    base_url = get_settings().rigzone_base_url

    def parse_html(self, html: str, limit: int = 50) -> list[ExtractedJob]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[ExtractedJob] = []

        for script in soup.select('script[type="application/ld+json"]'):
            text = script.get_text(strip=True)
            if "JobPosting" not in text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            payloads = payload if isinstance(payload, list) else [payload]
            for item in payloads:
                if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                    continue
                source_url = _string_or_none(item.get("url"))
                title = _string_or_none(item.get("title"))
                if not source_url or not title:
                    continue
                hiring_org = item.get("hiringOrganization") if isinstance(item.get("hiringOrganization"), dict) else {}
                jobs.append(
                    ExtractedJob(
                        source_name=self.source_name,
                        source_url=source_url,
                        external_job_id=_extract_external_id(source_url),
                        title=title,
                        company=_string_or_none(hiring_org.get("name")),
                        location=_extract_location(item.get("jobLocation")),
                        employment_type=_string_or_none(item.get("employmentType")),
                        posted_date=parse_date_safe(_string_or_none(item.get("datePosted"))),
                        raw_description=_string_or_none(item.get("description")),
                        source_payload=item,
                    )
                )
                if len(jobs) >= limit:
                    return jobs

        for card in soup.select("a[href*='/oil/jobs/postings/'], a[href*='/jobs/postings/']"):
            href = card.get("href")
            title = card.get_text(" ", strip=True)
            if not href or not title:
                continue
            absolute_url = urljoin(self.base_url, href)
            if any(job.source_url == absolute_url for job in jobs):
                continue
            jobs.append(
                ExtractedJob(
                    source_name=self.source_name,
                    source_url=absolute_url,
                    external_job_id=_extract_external_id(absolute_url),
                    title=re.sub(r"\s+", " ", title).strip(),
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


def _extract_external_id(source_url: str) -> str | None:
    match = re.search(r"(\d{4,})", source_url)
    return match.group(1) if match else None


def _extract_location(raw_location: object) -> str | None:
    if isinstance(raw_location, list):
        values = [_extract_location(item) for item in raw_location]
        values = [value for value in values if value]
        return ", ".join(values) if values else None
    if isinstance(raw_location, dict):
        address = raw_location.get("address")
        if isinstance(address, dict):
            fields = [
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("addressCountry"),
            ]
            parts = [str(field).strip() for field in fields if isinstance(field, str) and field.strip()]
            return ", ".join(parts) if parts else None
    return None

