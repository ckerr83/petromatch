from __future__ import annotations

from app.adapters.base import SourceAdapter
from app.adapters.energy_job_search import EnergyJobSearchAdapter
from app.adapters.rigzone import RigzoneAdapter
from app.schemas.source import SourceInfo


class SourceRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {
            EnergyJobSearchAdapter.source_name: EnergyJobSearchAdapter(),
            RigzoneAdapter.source_name: RigzoneAdapter(),
        }

    def list_sources(self) -> list[SourceInfo]:
        return [
            SourceInfo(
                name=adapter.source_name,
                display_name=adapter.display_name,
                base_url=adapter.base_url,
                supports_live_fetch=adapter.supports_live_fetch,
                notes="Adapters are conservative and may return zero jobs if parsing is uncertain.",
            )
            for adapter in self._adapters.values()
        ]

    def get(self, source_name: str) -> SourceAdapter:
        if source_name not in self._adapters:
            raise KeyError(f"Unknown source '{source_name}'.")
        return self._adapters[source_name]

    def all(self) -> list[SourceAdapter]:
        return list(self._adapters.values())

