from __future__ import annotations

from dataclasses import dataclass

from app.observability.metrics import increment


@dataclass(slots=True)
class RollupRebuildResult:
    usage_affected_rows: int = 0
    namespace_affected_rows: int = 0


class RollupService:
    def __init__(self, repository=None) -> None:
        self.repository = repository

    async def rebuild_usage(self) -> int:
        if self.repository is None:
            return 0
        affected_rows = await self.repository.rebuild_daily_usage_rollups()
        increment("rollups_usage_rebuilds")
        return affected_rows

    async def rebuild_namespaces(self) -> int:
        if self.repository is None:
            return 0
        affected_rows = await self.repository.rebuild_daily_namespace_rollups()
        increment("rollups_namespace_rebuilds")
        return affected_rows

    async def rebuild_all(self) -> RollupRebuildResult:
        return RollupRebuildResult(
            usage_affected_rows=await self.rebuild_usage(),
            namespace_affected_rows=await self.rebuild_namespaces(),
        )
