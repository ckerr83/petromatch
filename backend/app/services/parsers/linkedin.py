from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from bs4 import Tag

from app.services.parsers.base import EmailParseContext, ParsedOpportunity
from app.services.parsers.utils import (
    clean_line,
    closest_repeating_block,
    html_to_soup,
    is_ignored_link,
    lines_without_boilerplate,
    normalize_job_url,
    visible_text,
)
from app.utils.text import normalize_whitespace


class LinkedInEmailParser:
    source = "linkedin"

    def can_parse(self, context: EmailParseContext) -> bool:
        content = " ".join(
            part or ""
            for part in (context.sender, context.subject, context.html_body, context.plain_text_body)
        ).lower()
        return "linkedin" in content and (
            "linkedin.com/jobs" in content
            or "currentjobid" in content
            or "jobs you may be interested in" in content
            or "job alert" in content
        )

    def parse(self, context: EmailParseContext) -> list[ParsedOpportunity]:
        if context.html_body:
            opportunities = self._parse_html(context.html_body)
            if opportunities:
                return opportunities
        return self._parse_text(context.plain_text_body)

    def _parse_html(self, html: str) -> list[ParsedOpportunity]:
        soup = html_to_soup(html)
        opportunities: list[ParsedOpportunity] = []
        seen_urls: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = normalize_job_url(anchor.get("href"))
            anchor_text = clean_line(anchor.get_text(" ", strip=True))
            if not _is_linkedin_job_url(href) or is_ignored_link(href, anchor_text):
                continue
            if href in seen_urls:
                continue

            block = closest_repeating_block(anchor)
            block_text = visible_text(block)
            lines = lines_without_boilerplate(block_text)
            title, company, location = _infer_fields(anchor, lines)
            opportunities.append(
                ParsedOpportunity(
                    source=self.source,
                    job_title=title,
                    company=company,
                    location=location,
                    job_url=href,
                    posted_date=None,
                    raw_text=block_text or anchor_text or href,
                    external_id=_external_id_from_linkedin_url(href),
                )
            )
            seen_urls.add(href)

        return opportunities

    def _parse_text(self, text: str | None) -> list[ParsedOpportunity]:
        if not text:
            return []
        opportunities: list[ParsedOpportunity] = []
        seen_urls: set[str] = set()
        lines = lines_without_boilerplate(text)
        for index, line in enumerate(lines):
            urls = re.findall(r"https?://\S+", line)
            for raw_url in urls:
                url = normalize_job_url(raw_url.rstrip(").,]"))
                if not _is_linkedin_job_url(url) or url in seen_urls:
                    continue
                context_lines = lines[max(0, index - 3) : min(len(lines), index + 4)]
                title = _best_title_from_lines(context_lines)
                opportunities.append(
                    ParsedOpportunity(
                        source=self.source,
                        job_title=title,
                        company=None,
                        location=None,
                        job_url=url,
                        posted_date=None,
                        raw_text="\n".join(context_lines),
                        external_id=_external_id_from_linkedin_url(url),
                    )
                )
                seen_urls.add(url)
        return opportunities


def _is_linkedin_job_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return "linkedin.com" in parsed.netloc and (
        "/jobs/view" in parsed.path or "currentJobId" in parse_qs(parsed.query)
    )


def _external_id_from_linkedin_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    query_id = parse_qs(parsed.query).get("currentJobId")
    if query_id and query_id[0].isdigit():
        return query_id[0]
    match = re.search(r"/jobs/view/(\d+)", parsed.path)
    if match:
        return match.group(1)
    return None


def _infer_fields(anchor: Tag, lines: list[str]) -> tuple[str | None, str | None, str | None]:
    title, company, location = infer_linkedin_fields_from_text("\n".join(lines))
    if title or company or location:
        return title, company, location

    anchor_text = clean_line(anchor.get_text(" ", strip=True))
    title = _clean_title(anchor_text) if anchor_text and not _is_metadata_line(anchor_text) else _best_title_from_lines(lines)
    return title, None, None


def infer_linkedin_fields_from_text(raw_text: str | None) -> tuple[str | None, str | None, str | None]:
    lines = lines_without_boilerplate(raw_text)
    meaningful_lines = _meaningful_linkedin_lines(lines)
    company_location_index = next(
        (index for index, line in enumerate(meaningful_lines) if " · " in line),
        -1,
    )
    if company_location_index >= 0:
        company_location_line = meaningful_lines[company_location_index]
        company, location = [
            normalize_whitespace(part)
            for part in company_location_line.split(" · ", 1)
        ]
        title = _clean_title(" ".join(meaningful_lines[:company_location_index]))
        return title, company, location

    return _best_title_from_lines(meaningful_lines), None, None


def _best_title_from_lines(lines: list[str]) -> str | None:
    for line in lines:
        if _is_metadata_line(line):
            continue
        if re.search(r"\b(engineer|manager|specialist|analyst|operator|technician|supervisor|developer|consultant|advisor|director)\b", line, re.I):
            return _clean_title(line)
    for line in lines:
        if not _is_metadata_line(line):
            return _clean_title(line)
    return None


def _meaningful_linkedin_lines(lines: list[str]) -> list[str]:
    return [line for line in (clean_line(line) for line in lines) if line and not _is_metadata_line(line)]


def _is_metadata_line(line: str | None) -> bool:
    if not line:
        return True
    normalized = normalize_whitespace(line).lower()
    return bool(
        normalized
        and (
            re.fullmatch(r"actively recruiting", normalized)
            or re.fullmatch(r"easy apply", normalized)
            or re.fullmatch(r"\d+\s+connections?", normalized)
            or re.fullmatch(r"\d+\s+company alumni?", normalized)
            or re.fullmatch(r"\d+\s+company alums?", normalized)
            or re.fullmatch(r"\d+\s+school alumni?", normalized)
            or re.fullmatch(r"\d+\s+school alums?", normalized)
            or re.search(r"\b(view job|apply|see more|save|job alert|unsubscribe)\b", normalized)
        )
    )


def _clean_title(value: str | None) -> str | None:
    value = normalize_whitespace(value)
    if not value:
        return None
    value = re.sub(
        r"\s+(?:posted\s+)?(?:today|yesterday|\d+\s+(?:hour|hours|day|days|week|weeks|month|months)\s+ago)$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+\d{1,2}(?:,\s+\d{4})?$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"(?<=[A-Za-z0-9])(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+\d{1,2}(?:,\s+\d{4})?$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return normalize_whitespace(value)
