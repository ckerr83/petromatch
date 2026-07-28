from __future__ import annotations

import hashlib

from app.utils.text import normalize_text


def build_dedupe_fingerprint(title: str | None, company: str | None, location: str | None) -> str | None:
    normalized_parts = [normalize_text(part).lower() for part in (title, company, location) if normalize_text(part)]
    if not normalized_parts:
        return None
    return hashlib.sha1("|".join(normalized_parts).encode("utf-8")).hexdigest()

