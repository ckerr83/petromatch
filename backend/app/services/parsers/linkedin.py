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
    anchor_text = clean_line(anchor.get_text(" ", strip=True))
    title = anchor_text if anchor_text and not _looks_like_action(anchor_text) else _best_title_from_lines(lines)
    title_index = lines.index(title) if title in lines else -1

    company = None
    location = None
    following = lines[title_index + 1 :] if title_index >= 0 else lines
    for line in following[:5]:
        if _looks_like_location(line):
            location = line
            continue
        if company is None and not _looks_like_action(line) and line != title:
            company = line
            continue
    return title, company, location


def _best_title_from_lines(lines: list[str]) -> str | None:
    for line in lines:
        if _looks_like_action(line):
            continue
        if re.search(r"\b(engineer|manager|specialist|analyst|operator|technician|supervisor|developer|consultant|advisor|director)\b", line, re.I):
            return normalize_whitespace(line)
    for line in lines:
        if not _looks_like_action(line):
            return normalize_whitespace(line)
    return None


def _looks_like_action(line: str | None) -> bool:
    return bool(line and re.search(r"\b(view job|apply|see more|save|posted|alert)\b", line, re.I))


def _looks_like_location(line: str | None) -> bool:
    return bool(
        line
        and (
            "," in line
            or re.search(r"\b(remote|hybrid|onsite|united states|uk|uae|qatar|singapore|houston|london|dubai)\b", line, re.I)
        )
    )
