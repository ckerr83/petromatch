from __future__ import annotations

import re

from app.services.parsers.base import EmailParseContext, ParsedOpportunity
from app.services.parsers.utils import (
    clean_line,
    closest_repeating_block,
    html_to_soup,
    is_boilerplate_text,
    is_ignored_link,
    lines_without_boilerplate,
    normalize_job_url,
    visible_text,
)
from app.utils.text import normalize_whitespace


class GenericEmailParser:
    source = "generic"

    def can_parse(self, context: EmailParseContext) -> bool:
        return bool(context.html_body or context.plain_text_body)

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
            raw_text = anchor.get_text(" ", strip=True)
            url = normalize_job_url(anchor.get("href"))
            if not _looks_like_job_link(url, raw_text) or is_ignored_link(url, raw_text):
                continue
            if url in seen_urls:
                continue

            block = closest_repeating_block(anchor)
            block_text = visible_text(block)
            if not block_text or is_boilerplate_text(block_text):
                continue

            title, company, location = _infer_fields(raw_text, block_text)
            opportunities.append(
                ParsedOpportunity(
                    source=self.source,
                    job_title=title,
                    company=company,
                    location=location,
                    job_url=url,
                    posted_date=None,
                    raw_text=block_text,
                    external_id=_external_id_from_url(url),
                )
            )
            seen_urls.add(url)

        return opportunities

    def _parse_text(self, text: str | None) -> list[ParsedOpportunity]:
        if not text:
            return []
        opportunities: list[ParsedOpportunity] = []
        seen_urls: set[str] = set()
        lines = lines_without_boilerplate(text)
        for index, line in enumerate(lines):
            for raw_url in re.findall(r"https?://\S+", line):
                url = normalize_job_url(raw_url.rstrip(").,]"))
                if not _looks_like_job_link(url, line) or url in seen_urls:
                    continue
                context_lines = lines[max(0, index - 4) : min(len(lines), index + 5)]
                title, company, location = _infer_fields(line, "\n".join(context_lines))
                opportunities.append(
                    ParsedOpportunity(
                        source=self.source,
                        job_title=title,
                        company=company,
                        location=location,
                        job_url=url,
                        posted_date=None,
                        raw_text="\n".join(context_lines),
                        external_id=_external_id_from_url(url),
                    )
                )
                seen_urls.add(url)
        return opportunities


def _looks_like_job_link(url: str | None, text: str | None) -> bool:
    if not url:
        return False
    lowered_url = url.lower()
    lowered_text = (text or "").lower()
    positive_url_markers = ("/job", "jobs.", "/careers", "careers.", "/position", "/vacancy", "greenhouse.io", "lever.co")
    positive_text_markers = ("apply", "view job", "job", "role", "position", "opening")
    return any(marker in lowered_url for marker in positive_url_markers) or any(
        marker in lowered_text for marker in positive_text_markers
    )


def _infer_fields(anchor_text: str | None, block_text: str) -> tuple[str | None, str | None, str | None]:
    lines = lines_without_boilerplate(block_text)
    title = _title_from_anchor(anchor_text)
    if title is None:
        title = _title_from_lines(lines)

    company = None
    location = None
    title_index = lines.index(title) if title in lines else -1
    candidate_lines = lines[title_index + 1 :] if title_index >= 0 else lines
    for line in candidate_lines[:6]:
        if line == title or _looks_like_action(line):
            continue
        if location is None and _looks_like_location(line):
            location = line
            continue
        if company is None and not _looks_like_location(line):
            company = _company_from_line(line)
            continue
    return title, company, location


def _title_from_anchor(anchor_text: str | None) -> str | None:
    value = clean_line(anchor_text)
    if not value or _looks_like_action(value):
        return None
    return value


def _title_from_lines(lines: list[str]) -> str | None:
    for line in lines:
        if _looks_like_action(line):
            continue
        if re.search(r"\b(engineer|manager|specialist|analyst|operator|technician|supervisor|coordinator|consultant|advisor|director|lead)\b", line, re.I):
            return normalize_whitespace(line)
    return None


def _company_from_line(line: str) -> str | None:
    match = re.search(r"^(?:at|company:)\s+(.+)$", line, flags=re.I)
    if match:
        return normalize_whitespace(match.group(1))
    return normalize_whitespace(line)


def _looks_like_action(line: str | None) -> bool:
    return bool(line and re.search(r"\b(apply|view job|view role|see details|learn more|save job|posted)\b", line, re.I))


def _looks_like_location(line: str | None) -> bool:
    return bool(
        line
        and (
            "," in line
            or re.search(r"\b(remote|hybrid|onsite|on-site|houston|london|dubai|doha|singapore|aberdeen|riyadh)\b", line, re.I)
        )
    )


def _external_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"(?:job|jobs|position|requisition|req)[-/=](\d{4,})", url, re.I)
    if match:
        return match.group(1)
    return None
