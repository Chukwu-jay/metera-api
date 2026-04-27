from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class CacheHit:
    key: str
    payload: dict[str, Any]


class KVStore(Protocol):
    async def get_json(self, key: str) -> dict[str, Any] | None: ...
    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None: ...
    async def delete_prefix(self, prefix: str) -> int: ...


class ExactCache:
    def __init__(self, store: KVStore) -> None:
        self._store = store

    async def get(self, key: str) -> CacheHit | None:
        payload = await self._store.get_json(key)
        if not payload:
            return None
        return CacheHit(key=key, payload=payload)

    async def set(self, key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        await self._store.set_json(key, payload, ttl_seconds)

    async def invalidate_namespace(self, namespace: str) -> int:
        return await self._store.delete_prefix(f"{namespace}:")
