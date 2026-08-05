from __future__ import annotations

import json
import re
from datetime import date, datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.sources.base import SourceAdapter, SourceJob
from app.utils.text import normalize_whitespace

BASE_URL = "https://www.airswift.com"
JOBS_URL = f"{BASE_URL}/jobs"
USER_AGENT = "PetroMatch job-source ingestion/0.1 (Airswift public jobs; contact: local development)"
JOB_ID_RE = re.compile(r"-(\d{5,})/?$")
PAGE_COUNT_RE = re.compile(r"Found\s+\d+\s+jobs\s+on\s+(\d+)\s+pages", re.IGNORECASE)


class AirswiftSource(SourceAdapter):
    source = "airswift"
    display_name = "Airswift"

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        max_pages: int | None = None,
        fetch_details: bool = False,
    ) -> None:
        self.http_client = http_client
        self.max_pages = max_pages
        self.fetch_details = fetch_details

    def fetch_jobs(self) -> list[SourceJob]:
        owns_client = self.http_client is None
        client = self.http_client or httpx.Client(
            timeout=get_settings().request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        try:
            return self._fetch_jobs(client)
        finally:
            if owns_client:
                client.close()

    def _fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        first_response = client.get(JOBS_URL)
        first_response.raise_for_status()
        first_page = first_response.text
        total_pages = parse_total_pages(first_page)
        if self.max_pages is not None:
            total_pages = min(total_pages, self.max_pages)

        jobs = parse_listing_page(first_page)
        for page_num in range(2, total_pages + 1):
            response = client.get(JOBS_URL, params={"page_num": page_num})
            response.raise_for_status()
            page_jobs = parse_listing_page(response.text)
            if not page_jobs:
                break
            jobs.extend(page_jobs)

        unique_by_id: dict[str, SourceJob] = {}
        for job in jobs:
            if self.fetch_details:
                job = self._with_detail_metadata(client, job)
            unique_by_id.setdefault(job.external_id, job)
        return list(unique_by_id.values())

    def enrich_job(self, job: SourceJob) -> SourceJob:
        owns_client = self.http_client is None
        client = self.http_client or httpx.Client(
            timeout=get_settings().request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        try:
            return self._with_detail_metadata(client, job)
        finally:
            if owns_client:
                client.close()

    def _with_detail_metadata(self, client: httpx.Client, listing_job: SourceJob) -> SourceJob:
        response = client.get(listing_job.url)
        response.raise_for_status()
        detail_job = parse_detail_page(response.text, listing_job.url)
        if detail_job is None:
            return listing_job
        return detail_job


def parse_total_pages(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    summary = normalize_whitespace(soup.select_one(".c-card-job-header__summary").get_text(" ")) if soup.select_one(".c-card-job-header__summary") else None
    if summary:
        match = PAGE_COUNT_RE.search(summary)
        if match:
            return max(1, int(match.group(1)))

    pages = []
    for link in soup.select(".c-pagination__link[href*='page_num=']"):
        href = link.get("href", "")
        match = re.search(r"page_num=(\d+)", href)
        if match:
            pages.append(int(match.group(1)))
    return max(pages, default=1)


def parse_listing_page(html: str) -> list[SourceJob]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[SourceJob] = []
    for article in soup.select("article.c-card-job-item"):
        link = article.select_one(".c-card-job-item__title a[href]")
        if link is None:
            continue
        url = urljoin(BASE_URL, link["href"])
        external_id = external_id_from_url(url)
        title = normalize_whitespace(link.get_text(" "))
        if not external_id or not title:
            continue
        employment_type, posted_date = _listing_top_fields(article)
        location = _text_without_icon(article.select_one(".c-card-job-item__location"))
        summary = normalize_whitespace(article.select_one(".c-card-job-item__summary").get_text(" ")) if article.select_one(".c-card-job-item__summary") else ""
        jobs.append(
            SourceJob(
                source="airswift",
                external_id=external_id,
                title=title,
                company="Airswift",
                location=location,
                url=url,
                description=summary or title,
                posted_date=posted_date,
                employment_type=employment_type,
                source_reference=external_id,
                raw_metadata={"source_page": "listing"},
            )
        )
    return jobs


def parse_detail_page(html: str, url: str) -> SourceJob | None:
    soup = BeautifulSoup(html, "html.parser")
    job_posting = _job_posting_json(soup)
    stats = _detail_stats(soup)

    title = _json_text(job_posting.get("title")) if job_posting else None
    title = title or _selector_text(soup, ".c-jobs-article-header__title")
    if not title:
        return None

    canonical = _canonical_url(soup) or url
    reference = normalize_whitespace(stats.get("Job reference")) or external_id_from_url(canonical)
    if not reference:
        return None

    description = _json_text(job_posting.get("description")) if job_posting else None
    description = description or _selector_text(soup, ".c-jobs-article-content.o-content-editor")
    if not description:
        description = title

    location = normalize_whitespace(stats.get("Location")) or _location_from_json(job_posting) or _selector_text(
        soup, ".c-jobs-article-header__location"
    )
    employment_type = normalize_whitespace(stats.get("Employment type")) or _json_text(
        job_posting.get("employmentType") if job_posting else None
    )
    posted_date = _date_from_json(job_posting.get("datePosted") if job_posting else None) or _parse_date(
        stats.get("Date published")
    )
    salary = _salary_from_json(job_posting)

    raw_metadata: dict[str, Any] = {"detail_stats": stats}
    if job_posting:
        raw_metadata["job_posting"] = job_posting

    return SourceJob(
        source="airswift",
        external_id=reference,
        title=title,
        company="Airswift",
        location=location,
        url=canonical,
        description=description,
        posted_date=posted_date,
        employment_type=employment_type,
        salary=salary,
        source_reference=reference,
        raw_metadata=raw_metadata,
    )


def external_id_from_url(url: str) -> str | None:
    match = JOB_ID_RE.search(url)
    return match.group(1) if match else None


def _listing_top_fields(article: Any) -> tuple[str | None, date | None]:
    fields = [_text_without_icon(node) for node in article.select(".c-card-job-item__top-cell")]
    employment_type = fields[0] if fields else None
    posted_date = _parse_date(fields[1]) if len(fields) > 1 else None
    return employment_type, posted_date


def _text_without_icon(node: Any) -> str | None:
    if node is None:
        return None
    clone = BeautifulSoup(str(node), "html.parser")
    for tag in clone.select("img, svg"):
        tag.decompose()
    return normalize_whitespace(clone.get_text(" "))


def _selector_text(soup: BeautifulSoup, selector: str) -> str | None:
    node = soup.select_one(selector)
    return normalize_whitespace(node.get_text(" ")) if node else None


def _canonical_url(soup: BeautifulSoup) -> str | None:
    node = soup.select_one("link[rel='canonical'][href]")
    return node["href"] if node else None


def _detail_stats(soup: BeautifulSoup) -> dict[str, str]:
    stats: dict[str, str] = {}
    for item in soup.select(".c-jobs-article-stats__content"):
        label = item.find("strong")
        if label is None:
            continue
        key = normalize_whitespace(label.get_text(" "))
        label.extract()
        value = normalize_whitespace(item.get_text(" "))
        if key and value:
            stats[key] = value
    return stats


def _job_posting_json(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = parsed if isinstance(parsed, list) else [parsed]
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("@type") == "JobPosting":
                return candidate
    return None


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return normalize_whitespace(unescape(value))
    if isinstance(value, list):
        return normalize_whitespace(" ".join(str(item) for item in value))
    return normalize_whitespace(str(value))


def _location_from_json(job_posting: dict[str, Any] | None) -> str | None:
    if not job_posting:
        return None
    address = job_posting.get("jobLocation", {}).get("address", {})
    parts = [
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
    ]
    return normalize_whitespace(", ".join(str(part) for part in parts if part))


def _salary_from_json(job_posting: dict[str, Any] | None) -> str | None:
    if not job_posting:
        return None
    salary = job_posting.get("baseSalary")
    if not salary:
        return None
    return _json_text(salary)


def _date_from_json(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return _date_from_json(value)
