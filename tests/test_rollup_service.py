import pytest

from app.controlplane.services.rollup_service import RollupService


class FakeRollupRepository:
    async def rebuild_daily_usage_rollups(self):
        return 7

    async def rebuild_daily_namespace_rollups(self):
        return 11


@pytest.mark.asyncio
async def test_rollup_service_rebuild_all() -> None:
    service = RollupService(repository=FakeRollupRepository())

    result = await service.rebuild_all()

    assert result.usage_affected_rows == 7
    assert result.namespace_affected_rows == 11
