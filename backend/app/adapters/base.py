from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from app.adapters.types import ExtractedJob
from app.core.config import get_settings


class SourceAdapter(ABC):
    source_name: str
    display_name: str
    base_url: str
    supports_live_fetch: bool = True

    async def fetch_html(self) -> str:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(self.base_url, headers={"User-Agent": "PetroMatch/0.1"})
            response.raise_for_status()
            return response.text

    async def extract(self, raw_html: str | None = None, limit: int = 50) -> list[ExtractedJob]:
        html = raw_html if raw_html is not None else await self.fetch_html()
        return self.parse_html(html=html, limit=limit)

    @abstractmethod
    def parse_html(self, html: str, limit: int = 50) -> list[ExtractedJob]:
        raise NotImplementedError

