from __future__ import annotations

from difflib import SequenceMatcher

from app.utils.text import normalize_text


def similarity(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=normalize_text(left).lower(), b=normalize_text(right).lower()).ratio()
