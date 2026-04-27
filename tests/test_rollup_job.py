import pytest

from app.controlplane.jobs.rollups import run_rollup_rebuild_job


class FakeRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.warmed = False
        self.closed = False

    async def warmup(self) -> None:
        self.warmed = True

    async def close(self) -> None:
        self.closed = True


class FakeService:
    def __init__(self, repository=None) -> None:
        self.repository = repository

    async def rebuild_all(self):
        return type("Result", (), {"usage_affected_rows": 4, "namespace_affected_rows": 9})()


@pytest.mark.asyncio
async def test_run_rollup_rebuild_job(monkeypatch) -> None:
    repo_holder = {}

    def fake_repo_factory(dsn: str):
        repo = FakeRepository(dsn)
        repo_holder["repo"] = repo
        return repo

    monkeypatch.setattr("app.controlplane.jobs.rollups.PostgresRollupRepository", fake_repo_factory)
    monkeypatch.setattr("app.controlplane.jobs.rollups.RollupService", FakeService)

    result = await run_rollup_rebuild_job(dsn="postgresql://example")

    assert result == {"usage_affected_rows": 4, "namespace_affected_rows": 9}
    assert repo_holder["repo"].warmed is True
    assert repo_holder["repo"].closed is True
