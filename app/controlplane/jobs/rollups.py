from __future__ import annotations

from dataclasses import asdict, is_dataclass

from app.controlplane.repositories.rollups import PostgresRollupRepository
from app.controlplane.services.rollup_service import RollupService


async def run_rollup_rebuild_job(*, dsn: str) -> dict[str, int]:
    repository = PostgresRollupRepository(dsn)
    await repository.warmup()
    try:
        service = RollupService(repository=repository)
        result = await service.rebuild_all()
        if is_dataclass(result):
            return asdict(result)
        return {
            "usage_affected_rows": int(getattr(result, "usage_affected_rows", 0)),
            "namespace_affected_rows": int(getattr(result, "namespace_affected_rows", 0)),
        }
    finally:
        await repository.close()
