from __future__ import annotations

from app.controlplane.repositories.api_keys import PostgresApiKeyRepository


class RepositoryKeyResolver:
    def __init__(self, repository: PostgresApiKeyRepository) -> None:
        self.repository = repository

    async def resolve(self, presented_key: str | None):
        return await self.repository.resolve_key(presented_key)
