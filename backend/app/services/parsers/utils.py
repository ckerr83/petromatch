from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.utils.text import normalize_whitespace

BOILERPLATE_PATTERNS = (
    "unsubscribe",
    "privacy policy",
    "email preferences",
    "manage alerts",
    "view in browser",
    "terms of service",
)

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_NAMES = {
    "trk",
    "trackingid",
    "lipi",
    "midtoken",
    "midtok",
    "eid",
    "mc_cid",
    "mc_eid",
}


def html_to_soup(html: str | None) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def visible_text(node: Tag | BeautifulSoup | None) -> str | None:
    if node is None:
        return None
    text = node.get_text("\n", strip=True)
    lines = [normalize_whitespace(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def clean_line(value: str | None) -> str | None:
    value = normalize_whitespace(value)
    if not value:
        return None
    value = re.sub(r"^(new|promoted|actively recruiting)\s+", "", value, flags=re.IGNORECASE)
    return normalize_whitespace(value)


def is_boilerplate_text(value: str | None) -> bool:
    lowered = (value or "").lower()
    return any(pattern in lowered for pattern in BOILERPLATE_PATTERNS)


def normalize_job_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    query = parse_qs(parsed.query, keep_blank_values=True)
    filtered_query = {
        key: values
        for key, values in query.items()
        if key.lower() not in TRACKING_QUERY_NAMES
        and not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    }
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
        query=urlencode(filtered_query, doseq=True),
    )
    return urlunparse(normalized)


def is_ignored_link(url: str | None, text: str | None = None) -> bool:
    if not url:
        return True
    lowered_url = url.lower()
    lowered_text = (text or "").lower()
    if lowered_url.startswith(("mailto:", "tel:")):
        return True
    ignored_url_parts = (
        "unsubscribe",
        "email-preferences",
        "preferences",
        "privacy",
        "terms",
        "/help/",
        "/feed/",
        "/company/",
        "/school/",
        "/groups/",
        "/pulse/",
        "/learning/",
    )
    if any(part in lowered_url for part in ignored_url_parts):
        return True
    if is_boilerplate_text(lowered_text):
        return True
    return False


def closest_repeating_block(anchor: Tag) -> Tag:
    for parent in anchor.parents:
        if not isinstance(parent, Tag):
            continue
        text = visible_text(parent) or ""
        links = parent.find_all("a", href=True)
        if 20 <= len(text) <= 1200 and len(links) <= 8:
            return parent
    return anchor


def lines_without_boilerplate(text: str | None) -> list[str]:
    lines = [clean_line(line) for line in (text or "").splitlines()]
    return [line for line in lines if line and not is_boilerplate_text(line)]
